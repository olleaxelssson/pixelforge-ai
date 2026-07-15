"""Palette quantization and extraction (Stage C of the pipeline).

Pure numpy/Pillow image processing — deterministic and model-independent.
"""

from __future__ import annotations

import numpy as np
from PIL import Image

from pixelforge.palettes.model import RGB, Palette, rgb_to_hex

# 4x4 Bayer matrix, normalized to [-0.5, 0.5), used for ordered dithering.
_BAYER_4X4 = (
    np.array(
        [[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]],
        dtype=np.float32,
    )
    / 16.0
    - 0.5
)


def extract_palette(image: Image.Image, max_colors: int) -> list[RGB]:
    """Extract a dominant palette using Pillow's median-cut quantizer."""
    rgb = image.convert("RGB")
    quantized = rgb.quantize(colors=max_colors, method=Image.Quantize.MEDIANCUT)
    raw = quantized.getpalette() or []
    count = len(quantized.getcolors(maxcolors=max_colors * 4) or [])
    colors = [(raw[i * 3], raw[i * 3 + 1], raw[i * 3 + 2]) for i in range(min(max_colors, count))]
    return colors or [(0, 0, 0)]


def apply_palette(
    image: Image.Image,
    colors: list[RGB],
    ordered_dither: bool = False,
    dither_strength: float = 24.0,
) -> Image.Image:
    """Map every pixel to its nearest palette color, preserving alpha."""
    rgba = np.asarray(image.convert("RGBA"), dtype=np.float32)
    height, width = rgba.shape[:2]
    rgb = rgba[..., :3]
    alpha = rgba[..., 3:4]

    if ordered_dither:
        tiled = np.tile(_BAYER_4X4, (height // 4 + 1, width // 4 + 1))[:height, :width]
        rgb = np.clip(rgb + tiled[..., None] * dither_strength, 0, 255)

    palette = np.array(colors, dtype=np.float32)  # (n, 3)
    distances = np.linalg.norm(rgb[..., None, :] - palette[None, None, :, :], axis=-1)
    nearest = np.argmin(distances, axis=-1)
    mapped = palette[nearest]

    out = np.concatenate([mapped, alpha], axis=-1).astype(np.uint8)
    return Image.fromarray(out, "RGBA")


def palette_from_image(image: Image.Image, max_colors: int, palette_id: str) -> Palette:
    colors = extract_palette(image, max_colors)
    return Palette(
        id=palette_id,
        name=f"Extracted ({len(colors)} colors)",
        colors=[rgb_to_hex(c) for c in colors],
    )


def swap_palette(image: Image.Image, source: Palette, target: Palette) -> Image.Image:
    """Replace source palette colors with target colors by index (cycled)."""
    source_rgb = source.as_rgb()
    target_rgb = target.as_rgb()
    mapping = {src: target_rgb[i % len(target_rgb)] for i, src in enumerate(source_rgb)}
    rgba = np.asarray(image.convert("RGBA"), dtype=np.uint8).copy()
    for src, dst in mapping.items():
        mask = np.all(rgba[..., :3] == np.array(src, dtype=np.uint8), axis=-1)
        rgba[mask, 0], rgba[mask, 1], rgba[mask, 2] = dst
    return Image.fromarray(rgba, "RGBA")
