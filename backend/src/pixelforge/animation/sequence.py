"""Animation frame sequences (M3/M18, D-009): seed-anchored, palette-locked, QA'd.

Turns an :class:`AnimationState` action into a real multi-frame sprite sequence. Two mechanisms give
cross-frame consistency on any backend:

- **Seed anchoring** — every frame shares one seed; only the per-frame action description changes,
  so a diffusion backend keeps the same subject and varies the pose (deterministic on the mock too).
- **Palette lock** — the first frame's palette is reused for every later frame (the D-012/M8 lock
  via ``GenerationRequest.locked_palette_hex``), so colors never drift between frames.

Each frame optionally passes through the QA engine (D-013); frames assemble into a GIF and a sprite
sheet via :mod:`assembly`.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image
from pydantic import BaseModel, Field

from pixelforge.animation.actions import get_action
from pixelforge.animation.assembly import build_sprite_sheet, save_gif
from pixelforge.core.errors import UnknownRegistryKeyError
from pixelforge.core.models import GenerationRequest
from pixelforge.generation.pipeline import GenerationPipeline, ProgressCallback
from pixelforge.palettes.model import hex_to_rgb, rgb_to_hex
from pixelforge.qa.engine import QAEngine
from pixelforge.qa.models import DetectorContext, QAScores


class AnimationRequest(BaseModel):
    prompt: str
    action: str = "idle"
    mode: str = "character"
    style: str = "modern-indie"
    width: int = Field(default=32, ge=8, le=512)
    height: int = Field(default=32, ge=8, le=512)
    seed: int | None = None
    palette_id: str | None = None
    max_colors: int = Field(default=16, ge=2, le=256)
    frame_duration_ms: int = Field(default=120, ge=20, le=2000)
    run_qa: bool = False


class AnimationFrame(BaseModel):
    index: int
    filename: str
    seed: int
    description: str
    qa: QAScores | None = None


class AnimationResult(BaseModel):
    action: str
    action_name: str
    loop: bool
    frame_duration_ms: int
    palette_hex: list[str] = Field(default_factory=list)
    frames: list[AnimationFrame] = Field(default_factory=list)
    gif_filename: str
    sheet_filename: str


class AnimationSequence:
    def __init__(
        self,
        pipeline: GenerationPipeline,
        outputs_dir: Path,
        qa_engine: QAEngine | None = None,
    ) -> None:
        self._pipeline = pipeline
        self._outputs_dir = outputs_dir
        self._qa = qa_engine

    def generate(
        self, job_id: str, request: AnimationRequest, on_progress: ProgressCallback
    ) -> AnimationResult:
        action = get_action(request.action)
        if action is None:
            raise UnknownRegistryKeyError(f"unknown animation action: {request.action}")

        base_seed = request.seed if request.seed is not None else 0
        locked: list[str] | None = None
        frames: list[AnimationFrame] = []
        images: list[Image.Image] = []

        for index, description in enumerate(action.frame_descriptions):
            on_progress(f"frame {index + 1}/{action.frame_count}", index / action.frame_count * 90)
            frame_request = GenerationRequest(
                prompt=f"{request.prompt}, {description}",
                mode=request.mode,
                style=request.style,
                width=request.width,
                height=request.height,
                seed=base_seed,  # anchored: same seed across frames
                batch_size=1,
                palette_id=request.palette_id,
                max_colors=request.max_colors,
                locked_palette_hex=locked,
            )
            result = self._pipeline.run(f"{job_id}_f{index}", frame_request, lambda _s, _p: None)
            image_meta = result.images[0]
            if locked is None and request.palette_id is None:
                locked = image_meta.palette_hex  # lock frame 0's palette for the rest

            image = Image.open(self._outputs_dir / image_meta.filename).convert("RGBA")
            images.append(image)

            scores = None
            if self._qa is not None and request.run_qa:
                context = DetectorContext(
                    max_colors=request.max_colors,
                    subject=request.prompt,
                    palette=[hex_to_rgb(h) for h in image_meta.palette_hex],
                )
                scores = self._qa.run(image, context).scores

            frames.append(
                AnimationFrame(
                    index=index,
                    filename=image_meta.filename,
                    seed=image_meta.seed,
                    description=description,
                    qa=scores,
                )
            )

        on_progress("assemble", 95.0)
        gif_name = f"{job_id}.gif"
        sheet_name = f"{job_id}_sheet.png"
        save_gif(
            images, str(self._outputs_dir / gif_name), request.frame_duration_ms, loop=action.loop
        )
        build_sprite_sheet(images).save(self._outputs_dir / sheet_name)
        on_progress("done", 100.0)

        return AnimationResult(
            action=action.id,
            action_name=action.name,
            loop=action.loop,
            frame_duration_ms=request.frame_duration_ms,
            palette_hex=locked if locked is not None else _image_palette(images[0]),
            frames=frames,
            gif_filename=gif_name,
            sheet_filename=sheet_name,
        )


def _image_palette(image: Image.Image) -> list[str]:
    """The distinct opaque colors of a sprite, as hex (the shared animation palette)."""
    rgba = np.asarray(image.convert("RGBA"), dtype=np.uint8)
    opaque = rgba[rgba[..., 3] > 0][:, :3]
    colors = np.unique(opaque, axis=0) if len(opaque) else np.empty((0, 3), np.uint8)
    return [rgb_to_hex((int(c[0]), int(c[1]), int(c[2]))) for c in colors]
