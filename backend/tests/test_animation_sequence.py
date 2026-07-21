"""Animation sequence tests (M3/M18/M19): palette lock, seed anchoring, assembly, reference
chaining, per-frame consistency, API, CLI."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image

from pixelforge.animation.sequence import AnimationRequest, AnimationSequence
from pixelforge.cli import main
from pixelforge.core.errors import UnknownRegistryKeyError
from pixelforge.generation.backends.base import DiffusionSpec, GenerationBackend, ProgressFn
from pixelforge.generation.backends.registry import _BACKENDS
from pixelforge.generation.pipeline import GenerationPipeline
from pixelforge.memory.embeddings import MockEmbeddingBackend
from pixelforge.modes.registry import ModeRegistry
from pixelforge.palettes.model import rgb_to_hex
from pixelforge.palettes.service import PaletteService
from pixelforge.qa.engine import QAEngine
from pixelforge.styles.registry import StyleRegistry


def _sequence(outputs_dir: Path, qa: bool = False) -> AnimationSequence:
    outputs_dir.mkdir(parents=True, exist_ok=True)
    pipeline = GenerationPipeline(
        backend_name="mock",
        outputs_dir=outputs_dir,
        modes=ModeRegistry(),
        styles=StyleRegistry(),
        palettes=PaletteService(user_dir=outputs_dir / "palettes"),
    )
    return AnimationSequence(pipeline, outputs_dir, qa_engine=QAEngine() if qa else None)


def _frame_colors(path: Path) -> set[str]:
    rgba = np.asarray(Image.open(path).convert("RGBA"), dtype=np.uint8)
    opaque = rgba[rgba[..., 3] > 0][:, :3]
    return {rgb_to_hex((int(c[0]), int(c[1]), int(c[2]))) for c in np.unique(opaque, axis=0)}


def _request(**overrides) -> AnimationRequest:
    base: dict = dict(prompt="a knight", action="walk", width=24, height=24, seed=7)
    base.update(overrides)
    return AnimationRequest(**base)


def test_frame_count_matches_action(tmp_path) -> None:
    result = _sequence(tmp_path).generate("t", _request(action="walk"), lambda _s, _p: None)
    assert result.action == "walk" and len(result.frames) == 6 and result.loop is True


def test_palette_is_locked_across_frames(tmp_path) -> None:
    result = _sequence(tmp_path).generate("t", _request(), lambda _s, _p: None)
    locked = set(result.palette_hex)
    assert locked, "expected a locked palette"
    # Every frame draws only from the locked palette — colors never drift between frames.
    for frame in result.frames:
        assert _frame_colors(tmp_path / frame.filename) <= locked


def test_sequence_is_seed_anchored_deterministic(tmp_path) -> None:
    first = _sequence(tmp_path / "a").generate("t", _request(), lambda _s, _p: None)
    second = _sequence(tmp_path / "b").generate("t", _request(), lambda _s, _p: None)
    for fa, fb in zip(first.frames, second.frames, strict=True):
        pa = np.asarray(Image.open(tmp_path / "a" / fa.filename).convert("RGBA"))
        pb = np.asarray(Image.open(tmp_path / "b" / fb.filename).convert("RGBA"))
        assert np.array_equal(pa, pb)


def test_gif_and_sheet_are_assembled(tmp_path) -> None:
    result = _sequence(tmp_path).generate("t", _request(action="idle"), lambda _s, _p: None)
    with Image.open(tmp_path / result.gif_filename) as gif:
        assert getattr(gif, "n_frames", 1) == 4  # idle = 4 frames
    with Image.open(tmp_path / result.sheet_filename) as sheet:
        assert sheet.size == (24 * 4, 24)  # 4 frames laid out in a row


def test_per_frame_qa_runs_when_requested(tmp_path) -> None:
    result = _sequence(tmp_path, qa=True).generate(
        "t", _request(action="idle", run_qa=True), lambda _s, _p: None
    )
    assert all(frame.qa is not None for frame in result.frames)


def test_unknown_action_is_rejected(tmp_path) -> None:
    try:
        _sequence(tmp_path).generate("t", _request(action="nope"), lambda _s, _p: None)
        raise AssertionError("expected UnknownRegistryKeyError")
    except UnknownRegistryKeyError:
        pass


# --- API + CLI --------------------------------------------------------------


def test_animation_actions_endpoint(client) -> None:
    response = client.get("/api/animation/actions")
    assert response.status_code == 200
    ids = [a["id"] for a in response.json()]
    assert "walk" in ids and "idle" in ids


def test_animation_generate_endpoint(client) -> None:
    response = client.post(
        "/api/animation/generate",
        json={"prompt": "a knight", "action": "idle", "width": 16, "height": 16, "seed": 1},
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["frames"]) == 4
    assert body["gif_filename"].endswith(".gif") and body["palette_hex"]


def test_animation_endpoint_rejects_unknown_action(client) -> None:
    response = client.post("/api/animation/generate", json={"prompt": "x", "action": "nope"})
    assert response.status_code == 422


def test_cli_animate(tmp_path, capsys) -> None:
    code = main(
        [
            "animate",
            "a knight",
            "--action",
            "idle",
            "--size",
            "16",
            "--seed",
            "1",
            "-o",
            str(tmp_path),
        ]
    )
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert len(payload["frames"]) == 4
    assert Path(payload["gif_path"]).exists() and Path(payload["sheet_path"]).exists()


def test_cli_list_actions(capsys) -> None:
    assert main(["list", "actions"]) == 0
    actions = json.loads(capsys.readouterr().out)
    assert any(a["id"] == "walk" and a["frame_count"] == 6 for a in actions)


# --- M19: reference chaining + per-frame consistency ------------------------


class _SpyBackend(GenerationBackend):
    """Records whether each generate() call carried a reference image (img2img)."""

    name = "spy-ref"

    def __init__(self) -> None:
        self.references: list[bool] = []

    def is_available(self) -> bool:
        return True

    def generate(self, spec: DiffusionSpec, on_progress: ProgressFn) -> list[Image.Image]:
        self.references.append(spec.reference_image is not None)
        on_progress(1.0)
        return [Image.new("RGBA", (spec.resolution, spec.resolution), (100, 120, 180, 255))]


def _spy_sequence(outputs_dir: Path, spy: _SpyBackend) -> AnimationSequence:
    outputs_dir.mkdir(parents=True, exist_ok=True)
    _BACKENDS[spy.name] = spy
    pipeline = GenerationPipeline(
        backend_name=spy.name,
        outputs_dir=outputs_dir,
        modes=ModeRegistry(),
        styles=StyleRegistry(),
        palettes=PaletteService(user_dir=outputs_dir / "palettes"),
    )
    return AnimationSequence(pipeline, outputs_dir, embeddings=MockEmbeddingBackend())


def test_reference_chaining_feeds_previous_frame(tmp_path) -> None:
    spy = _SpyBackend()
    try:
        _spy_sequence(tmp_path, spy).generate(
            "t", _request(action="idle", reference_chaining=True), lambda _s, _p: None
        )
    finally:
        _BACKENDS.pop(spy.name, None)
    # Frame 1 has no reference; every later frame is chained off the previous one.
    assert spy.references == [False, True, True, True]


def test_reference_chaining_off_by_default(tmp_path) -> None:
    spy = _SpyBackend()
    try:
        _spy_sequence(tmp_path, spy).generate("t", _request(action="idle"), lambda _s, _p: None)
    finally:
        _BACKENDS.pop(spy.name, None)
    assert spy.references == [False, False, False, False]


def _consistency_sequence(outputs_dir: Path, threshold: float = 0.85) -> AnimationSequence:
    outputs_dir.mkdir(parents=True, exist_ok=True)
    pipeline = GenerationPipeline(
        backend_name="mock",
        outputs_dir=outputs_dir,
        modes=ModeRegistry(),
        styles=StyleRegistry(),
        palettes=PaletteService(user_dir=outputs_dir / "palettes"),
    )
    return AnimationSequence(
        pipeline, outputs_dir, embeddings=MockEmbeddingBackend(), drift_threshold=threshold
    )


def test_consistency_measured_per_frame(tmp_path) -> None:
    result = _consistency_sequence(tmp_path).generate(
        "t", _request(action="walk", check_consistency=True), lambda _s, _p: None
    )
    assert result.frames[0].consistency == 1.0  # frame 0 is the anchor
    assert all(-1.0 <= f.consistency <= 1.0 for f in result.frames)
    assert result.mean_consistency is not None and result.min_consistency is not None


def test_consistency_threshold_flags_drift(tmp_path) -> None:
    # A permissive threshold passes; a near-perfect one fails (mock frames genuinely differ).
    lenient = _consistency_sequence(tmp_path / "a", threshold=0.0).generate(
        "t", _request(action="idle", check_consistency=True), lambda _s, _p: None
    )
    strict = _consistency_sequence(tmp_path / "b", threshold=0.999).generate(
        "t", _request(action="idle", check_consistency=True), lambda _s, _p: None
    )
    assert lenient.consistent is True
    assert strict.consistent is False


def test_consistency_absent_when_not_requested(tmp_path) -> None:
    result = _consistency_sequence(tmp_path).generate(
        "t", _request(action="idle"), lambda _s, _p: None
    )
    assert result.mean_consistency is None
    assert all(f.consistency is None for f in result.frames)


def test_reference_chaining_does_not_change_mock_output(tmp_path) -> None:
    # The mock ignores reference images, so chaining must not alter frames (palette lock intact).
    plain = _consistency_sequence(tmp_path / "p").generate(
        "t", _request(action="idle"), lambda _s, _p: None
    )
    chained = _consistency_sequence(tmp_path / "c").generate(
        "t", _request(action="idle", reference_chaining=True), lambda _s, _p: None
    )
    for fp, fc in zip(plain.frames, chained.frames, strict=True):
        a = np.asarray(Image.open(tmp_path / "p" / fp.filename).convert("RGBA"))
        b = np.asarray(Image.open(tmp_path / "c" / fc.filename).convert("RGBA"))
        assert np.array_equal(a, b)
