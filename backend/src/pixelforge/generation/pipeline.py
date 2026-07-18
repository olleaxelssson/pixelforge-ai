"""The four-stage generation pipeline (see ARCHITECTURE.md and D-002).

Stage A: diffusion backend at model-native resolution
Stage B: grid snap to the target pixel size
Stage C: palette quantization (+ optional ordered dithering)
Stage D: cleanup (alpha binarization, orphan pixel removal)
"""

from __future__ import annotations

import base64
import io
import json
import random
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from PIL import Image

from pixelforge.core.models import (
    DitherMode,
    GeneratedImage,
    GenerationRequest,
    GenerationResult,
)
from pixelforge.core.scene_graph import SceneGraph
from pixelforge.generation.backends.base import DiffusionSpec
from pixelforge.generation.backends.registry import get_backend
from pixelforge.generation.plan_compiler import (
    compile_negative_prompt,
    compile_prompt,
    compile_silhouette_map,
)
from pixelforge.generation.prompt_builder import build_negative_prompt, build_prompt
from pixelforge.modes.registry import ModeRegistry
from pixelforge.palettes.model import rgb_to_hex
from pixelforge.palettes.quantize import apply_palette, extract_palette
from pixelforge.palettes.service import PaletteService
from pixelforge.pixelize import binarize_alpha, pixelize, remove_orphan_pixels
from pixelforge.qa.models import DetectorContext
from pixelforge.styles.registry import StyleRegistry

if TYPE_CHECKING:
    from pixelforge.agents.runtime import PlanningRuntime
    from pixelforge.qa.engine import QAEngine
    from pixelforge.qa.repair_loop import RepairLoop

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
        planner: PlanningRuntime | None = None,
        qa_engine: QAEngine | None = None,
        repair_loop: RepairLoop | None = None,
    ) -> None:
        self._backend_name = backend_name
        self._outputs_dir = outputs_dir
        self._modes = modes
        self._styles = styles
        self._palettes = palettes
        self._resolution = diffusion_resolution
        self._steps = diffusion_steps
        self._planner = planner
        self._qa = qa_engine
        self._repair_loop = repair_loop

    def run(
        self, job_id: str, request: GenerationRequest, on_progress: ProgressCallback
    ) -> GenerationResult:
        mode = self._modes.get(request.mode)
        style = self._styles.get(request.style)
        seed = request.seed if request.seed is not None else random.randrange(2**31)

        scene_graph: SceneGraph | None = None
        if self._planner is not None:
            scene_graph = self._planner.plan(request)
            prompt = compile_prompt(scene_graph, style)
            negative_prompt = compile_negative_prompt(scene_graph, style)
        else:
            prompt = build_prompt(request, mode, style)
            negative_prompt = build_negative_prompt(request, style)

        spec = DiffusionSpec(
            prompt=prompt,
            negative_prompt=negative_prompt,
            resolution=self._resolution,
            steps=self._steps,
            seed=seed,
            batch_size=request.batch_size,
            reference_image=_decode_reference(request.reference_image_base64),
            reference_strength=request.reference_strength,
        )
        if scene_graph is not None:
            control_map = compile_silhouette_map(scene_graph, self._resolution)
            if control_map is not None:
                spec.extra["silhouette_map"] = control_map

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

            if self._qa is not None or self._repair_loop is not None:
                context = DetectorContext(
                    max_colors=request.max_colors,
                    transparent_background=request.transparent_background,
                    palette=colors if request.palette_id else None,
                    lighting_direction=request.lighting_direction,
                )
                if self._qa is not None:
                    sprite, _ = self._qa.repair(sprite, context)
                if self._repair_loop is not None:
                    sprite, _ = self._repair_loop.run(sprite, context)

            filename = f"{job_id}_{index}.png"
            sprite.save(self._outputs_dir / filename)
            palette_hex = [rgb_to_hex((int(c[0]), int(c[1]), int(c[2]))) for c in colors]
            if scene_graph is not None:
                self._write_provenance(
                    scene_graph, prompt, negative_prompt, filename, seed + index, palette_hex
                )
            results.append(
                GeneratedImage(
                    filename=filename,
                    width=request.width,
                    height=request.height,
                    seed=seed + index,
                    palette_hex=palette_hex,
                )
            )

        on_progress("finalize", 100.0)
        return GenerationResult(images=results)

    def _write_provenance(
        self,
        scene_graph: SceneGraph,
        prompt: str,
        negative_prompt: str,
        filename: str,
        seed: int,
        palette_hex: list[str],
    ) -> None:
        """Provenance sidecar (D-009): everything needed to re-derive or audit this asset."""
        graph = scene_graph.model_copy(deep=True)
        graph.provenance.expanded_prompt = prompt
        graph.provenance.negative_prompt = negative_prompt
        graph.provenance.seed = seed
        graph.provenance.model_versions["diffusion_backend"] = self._backend_name
        sidecar = {
            "scene_graph": graph.canonical_dict(),
            "generation": {
                "filename": filename,
                "seed": seed,
                "palette_hex": palette_hex,
                "diffusion_resolution": self._resolution,
                "diffusion_steps": self._steps,
            },
        }
        path = self._outputs_dir / f"{Path(filename).stem}.provenance.json"
        path.write_text(json.dumps(sidecar, indent=2, sort_keys=True))


def _decode_reference(data: str | None) -> Image.Image | None:
    if not data:
        return None
    if "," in data:  # strip data-URI header if present
        data = data.split(",", 1)[1]
    return Image.open(io.BytesIO(base64.b64decode(data))).convert("RGBA")
