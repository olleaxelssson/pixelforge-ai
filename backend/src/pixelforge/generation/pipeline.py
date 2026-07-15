"""The four-stage generation pipeline (see ARCHITECTURE.md and D-002).

Stage A: diffusion backend at model-native resolution
Stage B: grid snap to the target pixel size
Stage C: palette quantization (+ optional ordered dithering)
Stage D: cleanup (alpha binarization, orphan pixel removal)
"""

from __future__ import annotations

import base64
import io
import random
from collections.abc import Callable
from pathlib import Path

from PIL import Image

from pixelforge.core.models import (
    DitherMode,
    GeneratedImage,
    GenerationRequest,
    GenerationResult,
)
from pixelforge.generation.backends.base import DiffusionSpec
from pixelforge.generation.backends.registry import get_backend
from pixelforge.generation.prompt_builder import build_negative_prompt, build_prompt
from pixelforge.modes.registry import ModeRegistry
from pixelforge.palettes.model import rgb_to_hex
from pixelforge.palettes.quantize import apply_palette, extract_palette
from pixelforge.palettes.service import PaletteService
from pixelforge.pixelize import binarize_alpha, pixelize, remove_orphan_pixels
from pixelforge.styles.registry import StyleRegistry

ProgressCallback = Callable[[str, float], None]


class GenerationPipeline:
    def __init__(
        self,
        backend_name: str,
        outputs_dir: Path,
        modes: ModeRegistry,
        styles: StyleRegistry,
        palettes: PaletteService,
        diffusion_resolution: int = 1024,
        diffusion_steps: int = 4,
    ) -> None:
        self._backend_name = backend_name
        self._outputs_dir = outputs_dir
        self._modes = modes
        self._styles = styles
        self._palettes = palettes
        self._resolution = diffusion_resolution
        self._steps = diffusion_steps

    def run(
        self, job_id: str, request: GenerationRequest, on_progress: ProgressCallback
    ) -> GenerationResult:
        mode = self._modes.get(request.mode)
        style = self._styles.get(request.style)
        seed = request.seed if request.seed is not None else random.randrange(2**31)

        spec = DiffusionSpec(
            prompt=build_prompt(request, mode, style),
            negative_prompt=build_negative_prompt(request, style),
            resolution=self._resolution,
            steps=self._steps,
            seed=seed,
            batch_size=request.batch_size,
            reference_image=_decode_reference(request.reference_image_base64),
            reference_strength=request.reference_strength,
        )

        on_progress("diffusion", 0.0)
        backend = get_backend(self._backend_name)
        raw_images = backend.generate(
            spec, lambda fraction: on_progress("diffusion", fraction * 60.0)
        )

        results = []
        for index, raw in enumerate(raw_images):
            base = 60.0 + (index / len(raw_images)) * 35.0
            on_progress("pixelize", base)
            sprite = pixelize(raw, request.width, request.height)

            on_progress("palette", base + 15.0 / len(raw_images))
            if request.palette_id:
                colors = self._palettes.get(request.palette_id).as_rgb()
            else:
                max_colors = style.default_max_colors or request.max_colors
                colors = extract_palette(sprite, min(request.max_colors, max_colors))
            sprite = apply_palette(
                sprite, colors, ordered_dither=request.dither is DitherMode.ORDERED
            )

            on_progress("cleanup", base + 25.0 / len(raw_images))
            if request.transparent_background:
                sprite = binarize_alpha(sprite)
                sprite = remove_orphan_pixels(sprite)
            else:
                sprite = sprite.convert("RGB").convert("RGBA")

            filename = f"{job_id}_{index}.png"
            sprite.save(self._outputs_dir / filename)
            results.append(
                GeneratedImage(
                    filename=filename,
                    width=request.width,
                    height=request.height,
                    seed=seed + index,
                    palette_hex=[rgb_to_hex((int(c[0]), int(c[1]), int(c[2]))) for c in colors],
                )
            )

        on_progress("finalize", 100.0)
        return GenerationResult(images=results)


def _decode_reference(data: str | None) -> Image.Image | None:
    if not data:
        return None
    if "," in data:  # strip data-URI header if present
        data = data.split(",", 1)[1]
    return Image.open(io.BytesIO(base64.b64decode(data))).convert("RGBA")
