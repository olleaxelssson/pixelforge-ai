"""Analysis orchestrator: run every analyzer over one image and assemble the result.

Returns both a rich JSON structure (for the UI and storage) and the derived values the importer
persists directly on the asset row (dimensions, palette size, grid scale, tileability, embedding,
perceptual hash, dominant colours) plus the LLM-facing digest.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np
from PIL import Image

from studylab.analysis.embed import embed
from studylab.analysis.llm_digest import build_digest
from studylab.analysis.notes import study_notes
from studylab.analysis.palette import analyze_palette
from studylab.analysis.pixelart import analyze_pixelart
from studylab.analysis.spritesheet import analyze_frames
from studylab.hashing import dhash


@dataclass
class AssetAnalysis:
    analysis: dict[str, Any]
    digest: str
    embedding: np.ndarray
    dominant: list[tuple[int, int, int]]
    phash: str
    columns: dict[str, Any] = field(default_factory=dict)


def analyze(image: Image.Image) -> AssetAnalysis:
    """Analyze a single (already-opened) image. Uses frame 0 for multi-frame images."""
    base = image
    if getattr(image, "n_frames", 1) > 1:
        image.seek(0)
        base = image
    rgba = np.asarray(base.convert("RGBA"), dtype=np.uint8)

    pal = analyze_palette(rgba)
    pa = analyze_pixelart(rgba, pal.dominant)
    fr = analyze_frames(image, rgba)

    analysis: dict[str, Any] = {
        "palette": asdict(pal),
        "pixel_art": asdict(pa),
        "frames": asdict(fr),
    }
    analysis["notes"] = study_notes(analysis)
    digest = build_digest(analysis)

    columns = {
        "width": int(rgba.shape[1]),
        "height": int(rgba.shape[0]),
        "format": (image.format or "").upper() or None,
        "frame_count": fr.frame_count,
        "has_alpha": int(pa.has_alpha),
        "transparent_ratio": pa.transparent_ratio,
        "palette_size": pal.color_count,
        "grid_scale": pa.grid_scale,
        "is_pixel_art": int(pa.is_pixel_art),
        "pixel_art_confidence": pa.confidence,
        "tileable_h": pa.tileable_h,
        "tileable_v": pa.tileable_v,
        "silhouette_coverage": pa.silhouette_coverage,
    }

    return AssetAnalysis(
        analysis=analysis,
        digest=digest,
        embedding=embed(rgba),
        dominant=pal.dominant,
        phash=dhash(base),
        columns=columns,
    )


def rebuild_digest(analysis: dict[str, Any], *, license: str | None, tags: list[str]) -> str:
    return build_digest(analysis, {"license": license, "tags": tags})
