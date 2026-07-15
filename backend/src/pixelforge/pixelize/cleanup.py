"""Stage D: post-quantization cleanup for crisp, game-ready sprites."""

from __future__ import annotations

import numpy as np
from PIL import Image


def binarize_alpha(image: Image.Image, threshold: int = 128) -> Image.Image:
    """Force fully-opaque or fully-transparent pixels (no soft alpha edges)."""
    rgba = np.asarray(image.convert("RGBA"), dtype=np.uint8).copy()
    alpha = rgba[..., 3]
    rgba[..., 3] = np.where(alpha >= threshold, 255, 0).astype(np.uint8)
    rgba[rgba[..., 3] == 0] = 0
    return Image.fromarray(rgba, "RGBA")


def remove_orphan_pixels(image: Image.Image) -> Image.Image:
    """Remove isolated opaque pixels with no 4-connected opaque neighbors."""
    rgba = np.asarray(image.convert("RGBA"), dtype=np.uint8).copy()
    opaque = rgba[..., 3] > 0
    padded = np.pad(opaque, 1, constant_values=False)
    neighbors = (
        padded[:-2, 1:-1].astype(np.uint8) + padded[2:, 1:-1] + padded[1:-1, :-2] + padded[1:-1, 2:]
    )
    orphan = opaque & (neighbors == 0)
    rgba[orphan] = 0
    return Image.fromarray(rgba, "RGBA")
