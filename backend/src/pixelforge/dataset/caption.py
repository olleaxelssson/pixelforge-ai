"""Deterministic auto-captioning (M4, D-001).

Reuses the palette intelligence (D-012) — no model — to describe a sprite for training: size,
palette size/readability, the dominant hue family, and how much of the frame the subject fills.
Same image → same caption, so manifests are reproducible.
"""

from __future__ import annotations

import numpy as np
from PIL import Image

from pixelforge.palettes.analysis import analyze_palette
from pixelforge.palettes.color_math import rgb_to_hue
from pixelforge.palettes.model import Palette, rgb_to_hex

_COLOR_CAP = 32
# Hue (degrees) → coarse color family, for a stable descriptor.
_HUE_NAMES = [
    (15, "red"),
    (45, "orange"),
    (70, "yellow"),
    (160, "green"),
    (200, "cyan"),
    (255, "blue"),
    (290, "purple"),
    (330, "magenta"),
    (360, "red"),
]


def _dominant_hue_name(rgb: np.ndarray, counts: np.ndarray) -> str:
    """Family of the most-common *saturated* color; 'monochrome' if the sprite is near-gray."""
    order = np.argsort(counts)[::-1]
    for idx in order:
        r, g, b = (int(v) for v in rgb[idx])
        if max(r, g, b) - min(r, g, b) < 24:
            continue  # skip near-gray colors
        hue = rgb_to_hue((r, g, b))
        return next(name for bound, name in _HUE_NAMES if hue <= bound)
    return "monochrome"


def caption_image(image: Image.Image) -> tuple[str, list[str]]:
    """Return ``(caption, tags)`` for a sprite."""
    rgba = np.asarray(image.convert("RGBA"), dtype=np.uint8)
    height, width = rgba.shape[:2]
    opaque_mask = rgba[..., 3] > 0
    coverage = float(opaque_mask.mean())
    opaque = rgba[opaque_mask][:, :3]

    if len(opaque) == 0:
        return "empty pixel-art sprite", ["pixel-art", "empty"]

    colors, counts = np.unique(opaque, axis=0, return_counts=True)
    capped = np.argsort(counts)[::-1][:_COLOR_CAP]
    hexes = [rgb_to_hex((int(c[0]), int(c[1]), int(c[2]))) for c in colors[capped]]
    analysis = analyze_palette(Palette(id="_ds", name="ds", colors=hexes))

    hue = _dominant_hue_name(colors, counts)
    fill = "full-frame" if coverage > 0.7 else "compact" if coverage < 0.25 else "centered"
    color_count = analysis.color_count

    caption = (
        f"pixel art sprite, {width}x{height}, {color_count}-color palette, "
        f"{hue} tones, {fill} subject"
    )
    tags = ["pixel-art", f"{width}x{height}", f"{color_count}-color", hue, fill]
    if analysis.readability_score >= 0.7:
        tags.append("high-contrast")
    return caption, tags
