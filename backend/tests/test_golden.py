"""Golden-image regression (M2, D-002) for the mock pipeline (Stage A→D).

The mock uses float value-noise and Pillow's ``resize``/median-cut ``quantize``, which are *not*
bit-reproducible across CPUs (SIMD/BLAS float order flips a few median-cut assignments) — so exact
pixels only match on the golden-authoring machine (``PIXELFORGE_STRICT_GOLDEN=1``). The always-on
check compares version-robust structure — shape, silhouette, palette budget — which still catches a
broken Stage B–D. Refresh with ``PIXELFORGE_UPDATE_GOLDEN=1``. Real-backend *quality* (not pixels)
is tracked by ``pixelforge benchmark``.
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


# Opaque colors must never exceed the pipeline's color budget (default max_colors).
_BUDGET = 16
# Silhouette (opaque mask) must agree with the golden this closely. Cross-machine float noise in the
# mock (np.exp/percentile) + Pillow median-cut flips a handful of boundary pixels; a *regression* in
# any Stage B–D changes the silhouette wholesale (well below this), so 0.80 separates the two.
_MIN_SILHOUETTE_AGREEMENT = 0.80


def test_golden_structure_is_stable(tmp_path) -> None:
    """Golden regression that survives cross-machine rendering noise.

    The mock pipeline (float value-noise → Pillow ``resize``/median-cut ``quantize``) is not
    bit-reproducible across CPUs even at identical library versions, so exact-pixel matching is
    only meaningful on the authoring machine (``PIXELFORGE_STRICT_GOLDEN=1``). Elsewhere we assert
    the version-robust structure — shape, silhouette agreement, palette budget — which still catches
    a broken Stage B–D. Refresh the goldens with ``PIXELFORGE_UPDATE_GOLDEN=1``.
    """
    update = os.environ.get("PIXELFORGE_UPDATE_GOLDEN") == "1"
    strict = os.environ.get("PIXELFORGE_STRICT_GOLDEN") == "1"
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

        if strict:
            assert np.array_equal(produced, golden), f"{name}: pixels drifted from golden"
            continue

        produced_opaque = produced[..., 3] > 0
        golden_opaque = golden[..., 3] > 0
        agreement = float((produced_opaque == golden_opaque).mean())
        assert agreement >= _MIN_SILHOUETTE_AGREEMENT, (
            f"{name}: silhouette agreement {agreement:.3f} < {_MIN_SILHOUETTE_AGREEMENT}"
        )
        colors = np.unique(produced[produced_opaque][:, :3], axis=0)
        assert len(colors) <= _BUDGET, f"{name}: {len(colors)} colors exceed budget {_BUDGET}"


def test_mock_pipeline_is_deterministic(tmp_path) -> None:
    """Same machine, two runs of the same case → identical (independent of the goldens)."""
    pipeline = _pipeline(tmp_path)
    first = _generate(pipeline, _CASES[0], tmp_path)
    second = _generate(pipeline, _CASES[0], tmp_path)
    assert np.array_equal(first, second)
