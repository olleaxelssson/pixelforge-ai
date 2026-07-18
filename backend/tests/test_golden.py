"""Golden-image regression (M2, D-002): the deterministic mock pipeline is byte-stable.

Same (prompt, mode, size, seed, palette) must always produce the same sprite. These goldens lock the
full Stage A→D pipeline (mock diffusion → pixelize → palette → cleanup) so an accidental change to
any stage is caught. Regenerate after an *intentional* change with ``PIXELFORGE_UPDATE_GOLDEN=1``.

The same harness measures a real backend's *quality* (see ``pixelforge benchmark``);
only the deterministic mock is pixel-locked here.
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
from PIL import Image

from pixelforge.core.models import GenerationRequest
from pixelforge.generation.pipeline import GenerationPipeline
from pixelforge.modes.registry import ModeRegistry
from pixelforge.palettes.service import PaletteService
from pixelforge.styles.registry import StyleRegistry

_GOLDEN_DIR = Path(__file__).parent / "golden"

# (name, prompt, mode, size, seed, palette_id)
_CASES = [
    ("character_24_1", "a knight with a flaming sword", "character", 24, 1, None),
    ("item_24_2", "health potion", "item", 24, 2, "8bit-console"),
    ("tileset_32_3", "a mossy dungeon tile", "tileset", 32, 3, None),
    ("text_16_4", "a slime monster", "text-to-pixel", 16, 4, None),
]


def _pipeline(outputs_dir: Path) -> GenerationPipeline:
    return GenerationPipeline(
        backend_name="mock",
        outputs_dir=outputs_dir,
        modes=ModeRegistry(),
        styles=StyleRegistry(),
        palettes=PaletteService(user_dir=outputs_dir / "palettes"),
    )


def _generate(pipeline: GenerationPipeline, case: tuple, outputs_dir: Path) -> np.ndarray:
    _name, prompt, mode, size, seed, palette_id = case
    request = GenerationRequest(
        prompt=prompt,
        mode=mode,
        width=size,
        height=size,
        seed=seed,
        batch_size=1,
        palette_id=palette_id,
    )
    result = pipeline.run("golden", request, lambda _s, _p: None)
    image = Image.open(outputs_dir / result.images[0].filename).convert("RGBA")
    return np.asarray(image, dtype=np.uint8)


def test_mock_pipeline_matches_goldens(tmp_path) -> None:
    update = os.environ.get("PIXELFORGE_UPDATE_GOLDEN") == "1"
    _GOLDEN_DIR.mkdir(exist_ok=True)
    pipeline = _pipeline(tmp_path)

    for case in _CASES:
        name = case[0]
        produced = _generate(pipeline, case, tmp_path)
        golden_path = _GOLDEN_DIR / f"{name}.png"

        if update:
            Image.fromarray(produced, "RGBA").save(golden_path)
            continue

        assert golden_path.exists(), (
            f"missing golden {golden_path}; run with PIXELFORGE_UPDATE_GOLDEN=1"
        )
        golden = np.asarray(Image.open(golden_path).convert("RGBA"), dtype=np.uint8)
        assert produced.shape == golden.shape, f"{name}: shape {produced.shape} != {golden.shape}"
        assert np.array_equal(produced, golden), f"{name}: pixels drifted from golden"


def test_mock_pipeline_is_deterministic(tmp_path) -> None:
    """Belt-and-suspenders: two runs of the same case are identical (independent of the goldens)."""
    pipeline = _pipeline(tmp_path)
    first = _generate(pipeline, _CASES[0], tmp_path)
    second = _generate(pipeline, _CASES[0], tmp_path)
    assert np.array_equal(first, second)
