"""QA repair-loop tests (D-013 Layer 2): convergence, non-regression, mask discipline, wiring."""

from __future__ import annotations

import base64
import io
import json

import numpy as np
from PIL import Image

from pixelforge.cli import main
from pixelforge.generation.backends.base import DiffusionSpec
from pixelforge.generation.backends.registry import get_backend
from pixelforge.qa.models import DetectorContext
from pixelforge.qa.repair_loop import (
    BackendRegionRegenerator,
    DeterministicInpaintRegenerator,
    RepairLoop,
)

# 10 isolated, distinct-colored specks inside a solid body — each is a size-1 broken cluster.
_SPECKS = {
    (4, 4): (255, 0, 0),
    (4, 7): (0, 255, 0),
    (4, 10): (255, 255, 0),
    (6, 5): (255, 0, 255),
    (6, 9): (0, 255, 255),
    (8, 5): (255, 128, 0),
    (8, 10): (128, 0, 255),
    (10, 5): (0, 128, 255),
    (10, 9): (255, 0, 128),
    (11, 7): (128, 255, 0),
}
_BODY = (70, 110, 180)


def _noisy_sprite() -> np.ndarray:
    arr = np.zeros((16, 16, 4), np.uint8)
    arr[3:13, 3:13] = [*_BODY, 255]  # solid opaque body
    for (y, x), color in _SPECKS.items():
        arr[y, x] = [*color, 255]
    return arr


def _img(arr: np.ndarray) -> Image.Image:
    return Image.fromarray(arr.astype(np.uint8), "RGBA")


def _rgba(image: Image.Image) -> np.ndarray:
    return np.asarray(image.convert("RGBA"), dtype=np.uint8)


def _context() -> DetectorContext:
    return DetectorContext(max_colors=4, transparent_background=True)


# --- convergence ------------------------------------------------------------


def test_loop_improves_a_failing_sprite() -> None:
    final, report = RepairLoop().run(_img(_noisy_sprite()), _context())

    assert report.initial.passed is False
    assert report.improved is True
    assert report.final.scores.overall > report.initial.scores.overall
    assert report.attempts and report.attempts[0].accepted is True

    # Every injected speck was regenerated back to the body color.
    fixed = _rgba(final)
    for y, x in _SPECKS:
        assert tuple(int(v) for v in fixed[y, x, :3]) == _BODY


def test_loop_is_bounded_by_max_iterations() -> None:
    _, report = RepairLoop(max_iterations=1).run(_img(_noisy_sprite()), _context())
    assert report.iterations <= 1


def test_loop_noop_on_clean_sprite() -> None:
    arr = np.zeros((16, 16, 4), np.uint8)
    arr[4:12, 4:12] = [70, 110, 180, 255]
    before = _rgba(_img(arr))
    final, report = RepairLoop().run(_img(arr), DetectorContext())
    assert report.initial.passed is True
    assert report.iterations == 0
    assert report.improved is False
    np.testing.assert_array_equal(_rgba(final), before)


# --- acceptance guard: a candidate that does not strictly improve is rejected --


class _NoOpRegenerator:
    """Returns the sprite unchanged -> zero score gain -> must be rejected (no churn)."""

    def regenerate(
        self, rgba: np.ndarray, mask: np.ndarray, context: DetectorContext
    ) -> np.ndarray:
        return rgba.copy()


def test_loop_rejects_a_non_improving_candidate() -> None:
    loop = RepairLoop(regenerator=_NoOpRegenerator())
    final, report = loop.run(_img(_noisy_sprite()), _context())
    # The one attempt is recorded but not accepted; the sprite is returned unchanged.
    assert report.attempts and report.attempts[0].accepted is False
    assert report.improved is False
    np.testing.assert_array_equal(_rgba(final), _noisy_sprite())


# --- mask discipline --------------------------------------------------------


def test_deterministic_regenerator_only_touches_masked_pixels() -> None:
    arr = _noisy_sprite()
    mask = np.zeros(arr.shape[:2], bool)
    mask[4, 4] = True  # a single speck
    out = DeterministicInpaintRegenerator().regenerate(arr, mask, _context())
    # The masked speck changed to the body color; every other pixel is byte-identical.
    assert tuple(int(v) for v in out[4, 4, :3]) == _BODY
    untouched = ~mask
    np.testing.assert_array_equal(out[untouched], arr[untouched])


def test_palette_snap_respects_locked_palette() -> None:
    arr = _noisy_sprite()
    mask = np.zeros(arr.shape[:2], bool)
    mask[4, 7] = True
    palette = [(70, 110, 180), (255, 255, 255)]
    out = DeterministicInpaintRegenerator().regenerate(arr, mask, DetectorContext(palette=palette))
    assert tuple(int(v) for v in out[4, 7, :3]) in {(70, 110, 180), (255, 255, 255)}


# --- backend regenerator path (real path, exercised with the mock backend) --


def test_backend_regenerator_preserves_pixels_outside_the_mask() -> None:
    arr = _noisy_sprite()
    mask = np.zeros(arr.shape[:2], bool)
    mask[4:6, 4:6] = True
    spec = DiffusionSpec(prompt="a knight", resolution=64, seed=3)
    out = BackendRegionRegenerator(get_backend("mock"), spec).regenerate(arr, mask, _context())
    assert out.dtype == np.uint8 and out.shape == arr.shape
    untouched = ~mask
    np.testing.assert_array_equal(out[untouched], arr[untouched])


# --- API + CLI --------------------------------------------------------------


def _b64(arr: np.ndarray) -> str:
    buffer = io.BytesIO()
    _img(arr).save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()


def test_qa_endpoint_repair_loop(client) -> None:
    response = client.post(
        "/api/qa",
        json={"image_base64": _b64(_noisy_sprite()), "max_colors": 4, "repair_loop": True},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["repair_loop"] is not None
    assert body["repair_loop"]["improved"] is True
    assert body["repaired_image_base64"] is not None


def test_cli_qa_repair_loop_writes_output(tmp_path, capsys) -> None:
    path = tmp_path / "noisy.png"
    _img(_noisy_sprite()).save(path)
    out = tmp_path / "fixed.png"
    assert main(["qa", str(path), "--repair-loop", "--max-colors", "4", "-o", str(out)]) == 0
    assert out.exists()
    payload = json.loads(capsys.readouterr().out)
    assert payload["repair_loop"]["improved"] is True
    fixed = _rgba(Image.open(out))
    assert tuple(int(v) for v in fixed[4, 4, :3]) == _BODY
