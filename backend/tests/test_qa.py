"""Pixel QA engine tests (D-013): deterministic detectors, repair, critic, API, CLI."""

from __future__ import annotations

import base64
import io
import json

import numpy as np
from PIL import Image

from pixelforge.cli import main
from pixelforge.qa.detectors.broken_clusters import BrokenClustersDetector
from pixelforge.qa.detectors.floating_pixels import FloatingPixelsDetector
from pixelforge.qa.detectors.light_direction import LightDirectionDetector
from pixelforge.qa.detectors.palette_overflow import PaletteOverflowDetector
from pixelforge.qa.detectors.pillow_shading import PillowShadingDetector
from pixelforge.qa.detectors.silhouette import SilhouetteDetector
from pixelforge.qa.engine import QAEngine
from pixelforge.qa.models import DetectorContext


def _img(arr: np.ndarray) -> Image.Image:
    return Image.fromarray(arr.astype(np.uint8), "RGBA")


def _square(size: int = 16) -> np.ndarray:
    arr = np.zeros((size, size, 4), np.uint8)
    arr[4:12, 4:12] = [200, 40, 40, 255]
    return arr


def _rgba(image: Image.Image) -> np.ndarray:
    return np.asarray(image.convert("RGBA"), dtype=np.uint8)


# --- detectors --------------------------------------------------------------


def test_floating_pixel_detected_and_repaired() -> None:
    arr = _square()
    arr[1, 1] = [0, 0, 255, 255]
    detector = FloatingPixelsDetector()
    findings = detector.detect(arr, DetectorContext())
    assert any(f.detector == "floating-pixel" for f in findings)
    repaired = detector.repair(arr, DetectorContext())
    assert repaired[1, 1, 3] == 0  # removed


def test_palette_overflow_detected_and_repaired() -> None:
    arr = np.zeros((16, 16, 4), np.uint8)
    for i in range(16):
        arr[:, i] = [i * 16, i * 16, i * 16, 255]
    context = DetectorContext(max_colors=4, transparent_background=False)
    detector = PaletteOverflowDetector()
    assert detector.detect(arr, context)
    repaired = detector.repair(arr, context)
    unique = np.unique(repaired[..., :3].reshape(-1, 3), axis=0)
    assert len(unique) <= 4


def test_broken_cluster_detected_and_repaired() -> None:
    arr = _square()
    arr[7, 7] = [0, 0, 255, 255]  # lone blue speck inside a red body
    context = DetectorContext(min_cluster_size=3)
    detector = BrokenClustersDetector()
    assert any(f.detector == "broken-cluster" for f in detector.detect(arr, context))
    repaired = detector.repair(arr, context)
    assert tuple(int(v) for v in repaired[7, 7, :3]) == (200, 40, 40)


def test_silhouette_flags_empty_sprite() -> None:
    arr = np.zeros((16, 16, 4), np.uint8)
    arr[0, 0] = [255, 255, 255, 255]  # 1 opaque pixel of 256 -> ~0.4%
    findings = SilhouetteDetector().detect(arr, DetectorContext())
    assert any(f.detector == "silhouette" and f.severity.value == "error" for f in findings)


def test_pillow_shading_detected_on_radial_gradient() -> None:
    size = 32
    yy, xx = np.mgrid[0:size, 0:size]
    dist = np.sqrt((yy - 15.5) ** 2 + (xx - 15.5) ** 2)
    val = np.clip(255 - dist * 12, 30, 255).astype(np.uint8)
    arr = np.zeros((size, size, 4), np.uint8)
    arr[..., 0] = val
    arr[..., 1] = val // 2
    arr[..., 2] = val // 3
    arr[..., 3] = np.where(dist < 14, 255, 0)
    assert PillowShadingDetector().detect(arr, DetectorContext())


def test_light_direction_flags_opposite_gradient() -> None:
    size = 20
    yy, xx = np.mgrid[0:size, 0:size]
    grad = ((xx + yy) * 6).clip(20, 255).astype(np.uint8)  # bright at bottom-right
    arr = np.zeros((size, size, 4), np.uint8)
    arr[..., 0] = arr[..., 1] = arr[..., 2] = grad
    arr[..., 3] = 255
    context = DetectorContext(transparent_background=False, lighting_direction="top-left")
    assert any(
        f.detector == "light-direction" for f in LightDirectionDetector().detect(arr, context)
    )


def test_light_direction_skipped_without_context() -> None:
    arr = _square()
    assert LightDirectionDetector().detect(arr, DetectorContext(lighting_direction=None)) == []


# --- engine -----------------------------------------------------------------


def test_engine_clean_sprite_passes() -> None:
    report = QAEngine().run(_img(_square()), DetectorContext())
    assert report.passed
    assert 0.0 <= report.scores.overall <= 1.0
    assert report.findings == []


def test_engine_repair_fixes_defects_and_reports() -> None:
    arr = _square()
    arr[1, 1] = [0, 0, 255, 255]  # floating
    arr[7, 7] = [10, 240, 10, 255]  # broken cluster
    repaired, report = QAEngine().repair(_img(arr), DetectorContext(min_cluster_size=3))
    fixed = _rgba(repaired)
    assert fixed[1, 1, 3] == 0
    assert tuple(int(v) for v in fixed[7, 7, :3]) == (200, 40, 40)
    assert not any(f.detector == "floating-pixel" for f in report.findings)


def test_engine_empty_sprite_fails() -> None:
    arr = np.zeros((16, 16, 4), np.uint8)
    report = QAEngine().run(_img(arr), DetectorContext())
    assert not report.passed


# --- API --------------------------------------------------------------------


def _b64(arr: np.ndarray) -> str:
    buffer = io.BytesIO()
    _img(arr).save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()


def test_qa_endpoint_reports(client) -> None:
    response = client.post("/api/qa", json={"image_base64": _b64(_square())})
    assert response.status_code == 200
    body = response.json()
    assert body["report"]["passed"] is True
    assert body["repaired_image_base64"] is None


def test_qa_endpoint_repairs(client) -> None:
    arr = _square()
    arr[1, 1] = [0, 0, 255, 255]
    response = client.post("/api/qa", json={"image_base64": _b64(arr), "repair": True})
    assert response.status_code == 200
    body = response.json()
    assert body["repaired_image_base64"] is not None
    restored = _rgba(Image.open(io.BytesIO(base64.b64decode(body["repaired_image_base64"]))))
    assert restored[1, 1, 3] == 0


def test_qa_endpoint_rejects_bad_image(client) -> None:
    assert client.post("/api/qa", json={"image_base64": "not-an-image"}).status_code == 422


# --- CLI --------------------------------------------------------------------


def test_cli_qa_reports(tmp_path, capsys) -> None:
    path = tmp_path / "sprite.png"
    _img(_square()).save(path)
    assert main(["qa", str(path)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert "scores" in payload and "passed" in payload


def test_cli_qa_repair_writes_output(tmp_path, capsys) -> None:
    arr = _square()
    arr[1, 1] = [0, 0, 255, 255]
    path = tmp_path / "dirty.png"
    _img(arr).save(path)
    out = tmp_path / "fixed.png"
    assert main(["qa", str(path), "--repair", "-o", str(out)]) == 0
    assert out.exists()
    assert _rgba(Image.open(out))[1, 1, 3] == 0
