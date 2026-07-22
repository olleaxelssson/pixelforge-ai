"""Seamless tiling (M22, D-001): make a sprite wrap without a visible seam.

A pure, deterministic **wrap-aware edge blend**. Within a band on each side, every pixel is
cross-mixed with its wrap-neighbour on the opposite edge, weighted so the mix is exactly ½·½ at
the very edge (making the two edges identical → the seam vanishes) and fades to zero toward the
interior (leaving the middle of the sprite untouched). Horizontal then vertical passes also make
the four corners converge to the average of all four, so a corner-to-corner tiling is seamless too.

Applied *before* palette quantization in the pipeline, so the blended edge colours snap back onto
the locked palette while staying equal on both sides (equal RGB quantizes to the same index).
"""

from __future__ import annotations

import numpy as np
from PIL import Image

DEFAULT_BLEND_FRACTION = 0.25


def make_tileable(
    image: Image.Image, blend_fraction: float = DEFAULT_BLEND_FRACTION
) -> Image.Image:
    """Return a copy of ``image`` whose opposite edges match, so it tiles without a seam."""
    rgba = np.asarray(image.convert("RGBA"), dtype=np.float64).copy()
    height, width = rgba.shape[:2]
    band_w = max(1, int(round(width * blend_fraction)))
    band_h = max(1, int(round(height * blend_fraction)))

    # Horizontal seam: blend the left/right bands toward each other.
    for i in range(band_w):
        weight = 0.5 * (1.0 - i / band_w)  # 0.5 at the edge, → 0 toward the interior
        left = rgba[:, i].copy()
        right = rgba[:, width - 1 - i].copy()
        rgba[:, i] = (1.0 - weight) * left + weight * right
        rgba[:, width - 1 - i] = (1.0 - weight) * right + weight * left

    # Vertical seam: blend the top/bottom bands (operates on the horizontally-blended array, so the
    # corners end up as the average of all four corners → seamless in both directions at once).
    for j in range(band_h):
        weight = 0.5 * (1.0 - j / band_h)
        top = rgba[j, :].copy()
        bottom = rgba[height - 1 - j, :].copy()
        rgba[j, :] = (1.0 - weight) * top + weight * bottom
        rgba[height - 1 - j, :] = (1.0 - weight) * bottom + weight * top

    return Image.fromarray(np.rint(rgba).astype(np.uint8), "RGBA")


def seam_metrics(rgba: np.ndarray) -> tuple[float, float]:
    """Mean per-channel edge-wrap discontinuity in [0, 1] as ``(horizontal, vertical)``.

    ``horizontal`` compares the left edge column with the right edge column (the pixels that touch
    when the sprite is tiled left-to-right); ``vertical`` compares the top and bottom rows. 0 = the
    edges match exactly (perfectly seamless); higher = a more visible seam.
    """
    pixels = rgba[..., :3].astype(np.float64)
    horizontal = float(np.abs(pixels[:, 0] - pixels[:, -1]).mean()) / 255.0
    vertical = float(np.abs(pixels[0, :] - pixels[-1, :]).mean()) / 255.0
    return horizontal, vertical


def seam_score(rgba: np.ndarray) -> float:
    """A single seamlessness score in [0, 1] (1 = perfectly seamless)."""
    horizontal, vertical = seam_metrics(rgba)
    return 1.0 - max(horizontal, vertical)
