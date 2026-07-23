"""Structural pixel-art analysis: grid scale, an is-pixel-art heuristic, outlines, dithering,
tileability and silhouette. All deterministic, numpy-only — the useful *local* mode.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


def _divisors(n: int, cap: int) -> list[int]:
    return [d for d in range(1, min(n, cap) + 1) if n % d == 0]


def detect_grid_scale(rgba: np.ndarray, cap: int = 32) -> int:
    """Largest block size ``s`` (>1) at which the image is constant within every s×s block.

    Detects sprites stored upscaled (each logical pixel drawn as an s×s block). Falls back to 1
    (native pixel art or non-blocky images).
    """
    h, w = rgba.shape[:2]
    candidates = sorted(set(_divisors(w, cap)) & set(_divisors(h, cap)), reverse=True)
    for s in candidates:
        if s == 1:
            break
        blocks = rgba.reshape(h // s, s, w // s, s, rgba.shape[2])
        # A block is uniform iff every pixel equals the block's top-left pixel.
        top_left = blocks[:, 0:1, :, 0:1, :]
        uniform = np.all(blocks == top_left, axis=(1, 3))  # (H', W', C) → collapse below
        frac = float(np.all(uniform, axis=-1).mean())
        if frac >= 0.98:
            return s
    return 1


def normalize_grid(rgba: np.ndarray, scale: int) -> np.ndarray:
    """Downsample an upscaled sprite back to its logical resolution (top-left of each block)."""
    if scale <= 1:
        return rgba
    return rgba[::scale, ::scale, :]


def _flatness(rgba: np.ndarray) -> float:
    """Fraction of horizontally/vertically adjacent pixel pairs that are identical (RGB)."""
    rgb = rgba[..., :3]
    if rgb.shape[0] < 2 or rgb.shape[1] < 2:
        return 1.0
    horiz = np.all(rgb[:, 1:] == rgb[:, :-1], axis=-1).mean()
    vert = np.all(rgb[1:, :] == rgb[:-1, :], axis=-1).mean()
    return float((horiz + vert) / 2)


@dataclass
class PixelArtAnalysis:
    grid_scale: int
    effective_width: int
    effective_height: int
    is_pixel_art: bool
    confidence: float
    flatness: float
    outline_ratio: float
    dithering: float
    tileable_h: float
    tileable_v: float
    silhouette_coverage: float
    silhouette_compactness: float
    has_alpha: bool
    transparent_ratio: float


def _seam(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.abs(a.astype(np.int16) - b.astype(np.int16)).mean()) / 255.0


def _outline_ratio(rgba: np.ndarray, darkest: np.ndarray | None) -> float:
    if darkest is None:
        return 0.0
    opaque = rgba[..., 3] > 0
    if not opaque.any():
        return 0.0
    padded = np.pad(opaque, 1, constant_values=False)
    # Boundary = opaque pixel adjacent to a transparent pixel or the frame edge.
    neighbours_opaque = (
        padded[:-2, 1:-1] & padded[2:, 1:-1] & padded[1:-1, :-2] & padded[1:-1, 2:]
    )
    boundary = opaque & ~neighbours_opaque
    if not boundary.any():
        return 0.0
    is_dark = np.all(rgba[..., :3] == darkest, axis=-1)
    return float((boundary & is_dark).sum() / boundary.sum())


def _dithering(rgba: np.ndarray) -> float:
    """Fraction of 2×2 blocks forming a two-colour diagonal checkerboard (a==d, b==c, a!=b)."""
    rgb = rgba[..., :3]
    h, w = rgb.shape[:2]
    if h < 2 or w < 2:
        return 0.0
    a, b = rgb[:-1, :-1], rgb[:-1, 1:]
    c, d = rgb[1:, :-1], rgb[1:, 1:]
    diag1 = np.all(a == d, axis=-1) & np.all(b == c, axis=-1)
    two_color = ~np.all(a == b, axis=-1)
    return float((diag1 & two_color).mean())


def analyze_pixelart(rgba: np.ndarray, dominant: list[tuple[int, int, int]]) -> PixelArtAnalysis:
    h, w = rgba.shape[:2]
    scale = detect_grid_scale(rgba)
    grid = normalize_grid(rgba, scale)
    gh, gw = grid.shape[:2]

    color_count = len(np.unique(grid[grid[..., 3] > 0][:, :3], axis=0)) if grid.size else 0
    flat = _flatness(grid)

    # Confidence blends: flat regions, small palette, small effective resolution.
    palette_score = float(np.clip((512 - color_count) / 512.0, 0.0, 1.0))
    eff = max(gw, gh)
    res_score = float(np.clip((512 - eff) / (512 - 64), 0.0, 1.0)) if eff > 64 else 1.0
    confidence = 0.45 * flat + 0.35 * palette_score + 0.20 * res_score
    is_pa = confidence >= 0.55

    darkest = None
    if dominant:
        darkest = min(dominant, key=lambda c: 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2])
        darkest = np.array(darkest, dtype=rgba.dtype)

    alpha = grid[..., 3]
    opaque_mask = alpha > 0
    coverage = float(opaque_mask.mean())
    # Compactness = how tightly the opaque pixels fill their bounding box.
    compactness = 0.0
    if opaque_mask.any():
        ys, xs = np.where(opaque_mask)
        bbox = (ys.max() - ys.min() + 1) * (xs.max() - xs.min() + 1)
        compactness = float(opaque_mask.sum() / bbox) if bbox else 0.0

    rgb = grid[..., :3]
    return PixelArtAnalysis(
        grid_scale=scale,
        effective_width=gw,
        effective_height=gh,
        is_pixel_art=bool(is_pa),
        confidence=round(float(confidence), 3),
        flatness=round(flat, 3),
        outline_ratio=round(_outline_ratio(grid, darkest), 3),
        dithering=round(_dithering(grid), 3),
        tileable_h=round(1.0 - _seam(rgb[:, 0], rgb[:, -1]), 3),
        tileable_v=round(1.0 - _seam(rgb[0, :], rgb[-1, :]), 3),
        silhouette_coverage=round(coverage, 3),
        silhouette_compactness=round(compactness, 3),
        has_alpha=bool((alpha < 255).any()),
        transparent_ratio=round(float((alpha == 0).mean()), 3),
    )
