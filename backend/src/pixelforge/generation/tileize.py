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


def lock_edges_to(
    image: Image.Image, reference: Image.Image, blend_fraction: float = DEFAULT_BLEND_FRACTION
) -> Image.Image:
    """Blend ``image``'s edge bands toward ``reference``'s so the two tiles share edges (M23).

    The weight is 1.0 at the very edge (the outermost ring becomes *exactly* the reference's) and
    fades to 0 toward the interior. When the reference already tiles (its left == right, top ==
    bottom), every image locked to it inherits those edges — so any two locked tiles abut cleanly
    *and* each still self-tiles. Interior content is left free to vary between variants.
    """
    img = np.asarray(image.convert("RGBA"), dtype=np.float64).copy()
    ref = np.asarray(reference.convert("RGBA"), dtype=np.float64)
    height, width = img.shape[:2]
    band_w = max(1, int(round(width * blend_fraction)))
    band_h = max(1, int(round(height * blend_fraction)))

    for i in range(band_w):
        weight = 1.0 - i / band_w  # 1.0 at the edge → 0 toward the interior
        img[:, i] = (1.0 - weight) * img[:, i] + weight * ref[:, i]
        img[:, width - 1 - i] = (1.0 - weight) * img[:, width - 1 - i] + weight * ref[
            :, width - 1 - i
        ]
    for j in range(band_h):
        weight = 1.0 - j / band_h
        img[j, :] = (1.0 - weight) * img[j, :] + weight * ref[j, :]
        img[height - 1 - j, :] = (1.0 - weight) * img[height - 1 - j, :] + weight * ref[
            height - 1 - j, :
        ]

    return Image.fromarray(np.rint(img).astype(np.uint8), "RGBA")


def cross_seam_metrics(a_rgba: np.ndarray, b_rgba: np.ndarray) -> tuple[float, float]:
    """How cleanly tile ``b`` abuts tile ``a``: b's left vs a's right, b's top vs a's bottom.

    Returns ``(horizontal, vertical)`` mean per-channel difference in [0, 1] — 0 means the tiles
    join without a seam when ``b`` is placed to the right of / below ``a``.
    """
    a = a_rgba[..., :3].astype(np.float64)
    b = b_rgba[..., :3].astype(np.float64)
    horizontal = float(np.abs(b[:, 0] - a[:, -1]).mean()) / 255.0
    vertical = float(np.abs(b[0, :] - a[-1, :]).mean()) / 255.0
    return horizontal, vertical


def edge_consistency(a_rgba: np.ndarray, b_rgba: np.ndarray) -> float:
    """A single [0, 1] score for how cleanly two tiles abut (1 = share edges exactly)."""
    horizontal, vertical = cross_seam_metrics(a_rgba, b_rgba)
    return 1.0 - max(horizontal, vertical)
