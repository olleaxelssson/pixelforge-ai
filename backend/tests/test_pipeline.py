import numpy as np
from PIL import Image

from pixelforge.core.models import GenerationRequest
from pixelforge.generation.backends.base import DiffusionSpec
from pixelforge.generation.backends.mock import MockBackend
from pixelforge.generation.backends.registry import get_backend
from pixelforge.generation.pipeline import GenerationPipeline
from pixelforge.generation.prompt_builder import build_negative_prompt, build_prompt
from pixelforge.modes.registry import ModeRegistry
from pixelforge.palettes.service import PaletteService
from pixelforge.styles.registry import StyleRegistry


def _pipeline(tmp_path):
    return GenerationPipeline(
        backend_name="mock",
        outputs_dir=tmp_path,
        modes=ModeRegistry(),
        styles=StyleRegistry(),
        palettes=PaletteService(user_dir=tmp_path / "palettes"),
        diffusion_resolution=128,
    )


def test_mock_backend_deterministic():
    backend = MockBackend()
    spec = DiffusionSpec(prompt="knight", resolution=64, seed=42)
    a = backend.generate(spec, lambda _: None)[0]
    b = backend.generate(spec, lambda _: None)[0]
    assert np.array_equal(np.asarray(a), np.asarray(b))


def test_registry_auto_falls_back_without_ml():
    backend = get_backend("auto")
    assert backend.name in ("mock", "flux-schnell")


def test_pipeline_produces_target_size(tmp_path):
    request = GenerationRequest(prompt="slime monster", width=32, height=32, seed=7)
    result = _pipeline(tmp_path).run("job1", request, lambda stage, pct: None)
    assert len(result.images) == 1
    image = Image.open(tmp_path / result.images[0].filename)
    assert image.size == (32, 32)


def test_pipeline_tileable_produces_seamless_sprite(tmp_path):
    from pixelforge.generation.tileize import seam_score

    request = GenerationRequest(
        prompt="grass texture", mode="tileset", width=32, height=32, seed=3, tileable=True
    )
    result = _pipeline(tmp_path).run("tile", request, lambda stage, pct: None)
    image = Image.open(tmp_path / result.images[0].filename)
    rgba = np.asarray(image.convert("RGBA"))
    # Edges match after quantization (equal RGB → same palette index), so the seam is gone.
    assert np.array_equal(rgba[:, 0, :3], rgba[:, -1, :3])
    assert np.array_equal(rgba[0, :, :3], rgba[-1, :, :3])
    assert seam_score(rgba) == 1.0


def test_pipeline_tileable_is_opt_in(tmp_path):
    """With the flag off, the tileize step never runs — output is byte-identical to the baseline."""
    off = GenerationRequest(prompt="hero sprite", mode="character", width=32, height=32, seed=8)
    on = off.model_copy(update={"tileable": True})
    pipeline = _pipeline(tmp_path)
    a = np.asarray(
        Image.open(tmp_path / pipeline.run("a", off, lambda s, p: None).images[0].filename)
    )
    b = np.asarray(
        Image.open(tmp_path / pipeline.run("b", on, lambda s, p: None).images[0].filename)
    )
    assert not np.array_equal(a, b)  # the flag changes the edges


def test_pipeline_respects_palette_lock(tmp_path):
    request = GenerationRequest(
        prompt="hero",
        width=16,
        height=16,
        seed=1,
        palette_id="monochrome-handheld",
        style="gameboy-inspired",
    )
    result = _pipeline(tmp_path).run("job2", request, lambda stage, pct: None)
    image = np.asarray(Image.open(tmp_path / result.images[0].filename))
    opaque = image[image[..., 3] > 0][..., :3]
    allowed = {(0x0F, 0x24, 0x18), (0x2F, 0x5E, 0x3C), (0x79, 0xA8, 0x6A), (0xC4, 0xDE, 0xA1)}
    found = {tuple(pixel) for pixel in opaque.tolist()}
    assert found <= allowed


def test_pipeline_batch(tmp_path):
    request = GenerationRequest(prompt="sword", width=16, height=16, seed=3, batch_size=3)
    result = _pipeline(tmp_path).run("job3", request, lambda stage, pct: None)
    assert len(result.images) == 3


def test_pipeline_reports_progress(tmp_path):
    stages = []
    request = GenerationRequest(prompt="shield", width=16, height=16, seed=4)
    _pipeline(tmp_path).run("job4", request, lambda stage, pct: stages.append(stage))
    assert "diffusion" in stages and "finalize" in stages


def test_prompt_builder_combines_mode_and_style():
    request = GenerationRequest(prompt="fire dragon", mode="creature", style="nes-inspired")
    modes, styles = ModeRegistry(), StyleRegistry()
    prompt = build_prompt(request, modes.get("creature"), styles.get("nes-inspired"))
    assert "fire dragon" in prompt
    assert "8-bit pixel art" in prompt
    negative = build_negative_prompt(request, styles.get("nes-inspired"))
    assert "blurry" in negative
