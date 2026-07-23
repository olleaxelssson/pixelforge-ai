"""Animation frames and sprite-sheet layout detection.

Two independent signals:
- **Animation**: multi-frame GIF/APNG → real frames read from the file.
- **Sheet**: a static image that is a strip (one side an integer multiple of the other) or has a
  regular grid of fully-transparent gutters. Conservative on purpose — a single sprite is *not*
  reported as a sheet just because its size happens to be divisible.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image


@dataclass
class FrameAnalysis:
    frame_count: int
    is_animation: bool
    is_sheet: bool
    columns: int
    rows: int
    cell_w: int
    cell_h: int


def _gutter_lines(is_empty: np.ndarray) -> list[int]:
    """Indices of fully-empty lines (transparent gutters)."""
    return [i for i, empty in enumerate(is_empty) if empty]


def _regular_grid(size: int, gutters: list[int]) -> int | None:
    """If gutters partition ``size`` into >1 equal cells, return the cell length."""
    if not gutters:
        return None
    # Consider interior gutters only; require even spacing.
    interior = [g for g in gutters if 0 < g < size - 1]
    if not interior:
        return None
    # Collapse consecutive gutter indices to single separators.
    seps: list[int] = []
    for g in interior:
        if not seps or g > seps[-1] + 1:
            seps.append(g)
    if not seps:
        return None
    cell = seps[0]
    if cell < 4:
        return None
    expected = list(range(cell, size, cell + 1))
    return cell if len(seps) >= 1 and size % (cell + 1) in (0, cell) else (cell if expected else None)


def analyze_frames(image: Image.Image, rgba: np.ndarray) -> FrameAnalysis:
    n_frames = getattr(image, "n_frames", 1)
    if n_frames and n_frames > 1:
        return FrameAnalysis(int(n_frames), True, False, 1, 1, image.width, image.height)

    h, w = rgba.shape[:2]

    # Strip: one dimension is a clean multiple (>=2) of the other.
    if h > 0 and w % h == 0 and w // h >= 2:
        cols = w // h
        return FrameAnalysis(cols, False, True, cols, 1, h, h)
    if w > 0 and h % w == 0 and h // w >= 2:
        rows = h // w
        return FrameAnalysis(rows, False, True, 1, rows, w, w)

    # Gutter grid: fully-transparent separator rows/columns.
    alpha = rgba[..., 3]
    empty_rows = (alpha == 0).all(axis=1)
    empty_cols = (alpha == 0).all(axis=0)
    cell_h = _regular_grid(h, _gutter_lines(empty_rows))
    cell_w = _regular_grid(w, _gutter_lines(empty_cols))
    if cell_h and cell_w:
        rows = max(1, (h + 1) // (cell_h + 1))
        cols = max(1, (w + 1) // (cell_w + 1))
        if rows * cols > 1:
            return FrameAnalysis(rows * cols, False, True, cols, rows, cell_w, cell_h)

    return FrameAnalysis(1, False, False, 1, 1, w, h)


def read_gif_frames(image: Image.Image, limit: int = 64) -> list[Image.Image]:
    """Return up to ``limit`` RGBA frames of an animated image."""
    frames: list[Image.Image] = []
    n = getattr(image, "n_frames", 1)
    for i in range(min(n, limit)):
        image.seek(i)
        frames.append(image.convert("RGBA"))
    return frames
