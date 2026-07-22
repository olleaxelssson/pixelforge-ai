"""Tileset service (M23, D-001): a coherent, seam-locked terrain family.

Builds on M22's seamless single-tile path. Given one prompt it generates a *base* terrain tile plus
N variants that all **share the base's edges**, so any two tiles in the set abut without a seam and
each still tiles by itself. Coherence comes from the same mechanisms the animation sequence uses for
frames:

- **Seed anchoring** — the base uses ``seed``; variant *i* uses ``seed + i``, so the family varies
  but is fully reproducible (deterministic on the mock backend too).
- **Palette lock** — the base's palette is reused for every variant (D-012/M8 lock via
  ``GenerationRequest.locked_palette_hex``), so colours never drift across the set.
- **Edge lock** — every variant is generated seamless (``tileable``), then its edge band is locked
  to the base's (``tileize.lock_edges_to``) and re-quantized back onto the palette. Consistency is
  measured with the M22 seam metrics (``edge_consistency``).

The variants assemble straight into the 47-tile Wang/blob sheet (the exporter cycles them across the
cells), so one call yields a paintable, engine-ready auto-tile set.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image
from pydantic import BaseModel, Field

from pixelforge.core.models import GenerationRequest
from pixelforge.exporters.base import ExportAsset, ExportOptions
from pixelforge.exporters.wang_blob import WangBlobExporter
from pixelforge.generation.pipeline import GenerationPipeline, ProgressCallback
from pixelforge.generation.tileize import edge_consistency, lock_edges_to, seam_score
from pixelforge.palettes.model import hex_to_rgb, rgb_to_hex
from pixelforge.palettes.quantize import apply_palette

_MAX_VARIANTS = 16


class TileSetRequest(BaseModel):
    prompt: str
    variants: int = Field(default=4, ge=1, le=_MAX_VARIANTS)
    mode: str = "tileset"
    style: str = "modern-indie"
    width: int = Field(default=32, ge=8, le=512)
    height: int = Field(default=32, ge=8, le=512)
    seed: int | None = None
    palette_id: str | None = None
    max_colors: int = Field(default=16, ge=2, le=256)


class TileVariant(BaseModel):
    index: int
    filename: str
    seed: int
    seam_score: float  # how well this tile tiles by itself (1 = seamless)
    edge_consistency: float  # how cleanly it abuts the base tile (1 = shares edges exactly)


class TileSetResult(BaseModel):
    prompt: str
    variant_count: int
    palette_hex: list[str] = Field(default_factory=list)
    base_seed: int
    tiles: list[TileVariant] = Field(default_factory=list)
    sheet_filename: str
    mean_edge_consistency: float
    min_edge_consistency: float
    coherent: bool  # every variant abuts the base above the coherence threshold


class TileSet:
    def __init__(
        self,
        pipeline: GenerationPipeline,
        outputs_dir: Path,
        coherence_threshold: float = 0.9,
    ) -> None:
        self._pipeline = pipeline
        self._outputs_dir = outputs_dir
        self._coherence_threshold = coherence_threshold

    def generate(
        self, job_id: str, request: TileSetRequest, on_progress: ProgressCallback
    ) -> TileSetResult:
        base_seed = request.seed if request.seed is not None else 0
        count = request.variants
        locked: list[str] | None = None
        base_rgba: np.ndarray | None = None
        tiles: list[TileVariant] = []
        images: list[Image.Image] = []

        for index in range(count):
            on_progress(f"variant {index + 1}/{count}", index / count * 90)
            variant_request = GenerationRequest(
                prompt=request.prompt,
                mode=request.mode,
                style=request.style,
                width=request.width,
                height=request.height,
                seed=base_seed + index,  # anchored family: base seed + variant offset
                batch_size=1,
                palette_id=request.palette_id,
                max_colors=request.max_colors,
                locked_palette_hex=locked,
                tileable=True,  # each variant is seamless on its own
                transparent_background=False,  # terrain tiles are opaque and fill the frame
            )
            result = self._pipeline.run(f"{job_id}_v{index}", variant_request, lambda _s, _p: None)
            meta = result.images[0]
            if locked is None and request.palette_id is None:
                locked = meta.palette_hex  # lock the base's palette for every later variant

            image = Image.open(self._outputs_dir / meta.filename).convert("RGBA")
            if base_rgba is None:
                base_rgba = np.asarray(image, dtype=np.uint8)  # variant 0 is the edge anchor
                consistency = 1.0
            else:
                # Lock this variant's edges to the base, then snap back onto the locked palette.
                colors = [hex_to_rgb(h) for h in (locked or meta.palette_hex)]
                image = apply_palette(
                    lock_edges_to(image, Image.fromarray(base_rgba, "RGBA")), colors
                )
                image.save(self._outputs_dir / meta.filename)
                consistency = round(edge_consistency(base_rgba, np.asarray(image)), 3)

            images.append(image)
            tiles.append(
                TileVariant(
                    index=index,
                    filename=meta.filename,
                    seed=meta.seed,
                    seam_score=round(seam_score(np.asarray(image)), 3),
                    edge_consistency=consistency,
                )
            )

        on_progress("assemble", 95.0)
        sheet_paths = WangBlobExporter().export(
            ExportAsset(frames=images), ExportOptions(base_name=job_id), self._outputs_dir
        )
        sheet_filename = sheet_paths[0].name
        on_progress("done", 100.0)

        scores = [t.edge_consistency for t in tiles]
        palette_hex = locked if locked is not None else _image_palette(images[0])
        return TileSetResult(
            prompt=request.prompt,
            variant_count=count,
            palette_hex=palette_hex,
            base_seed=base_seed,
            tiles=tiles,
            sheet_filename=sheet_filename,
            mean_edge_consistency=round(sum(scores) / len(scores), 3),
            min_edge_consistency=round(min(scores), 3),
            coherent=min(scores) >= self._coherence_threshold,
        )


def _image_palette(image: Image.Image) -> list[str]:
    rgba = np.asarray(image.convert("RGBA"), dtype=np.uint8)
    opaque = rgba[rgba[..., 3] > 0][:, :3]
    colors = np.unique(opaque, axis=0) if len(opaque) else np.empty((0, 3), np.uint8)
    return [rgb_to_hex((int(c[0]), int(c[1]), int(c[2]))) for c in colors]
