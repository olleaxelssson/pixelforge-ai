"""Stage B: snap a high-resolution diffusion output onto the target pixel grid.

For each target cell we take a robust central-region average of the source
pixels it covers, which keeps edges crisper than plain box downsampling while
avoiding the noise sensitivity of single-point nearest-neighbor sampling.
"""

from __future__ import annotations

import numpy as np
from PIL import Image


def pixelize(image: Image.Image, target_width: int, target_height: int) -> Image.Image:
    source = np.asarray(image.convert("RGBA"), dtype=np.float32)
    src_h, src_w = source.shape[:2]

    x_edges = np.linspace(0, src_w, target_width + 1)
    y_edges = np.linspace(0, src_h, target_height + 1)

    out = np.zeros((target_height, target_width, 4), dtype=np.float32)
    for ty in range(target_height):
        y0, y1 = int(y_edges[ty]), max(int(y_edges[ty + 1]), int(y_edges[ty]) + 1)
        for tx in range(target_width):
            x0, x1 = int(x_edges[tx]), max(int(x_edges[tx + 1]), int(x_edges[tx]) + 1)
            cell = source[y0:y1, x0:x1].reshape(-1, 4)
            out[ty, tx] = _robust_cell_color(cell)

    return Image.fromarray(out.astype(np.uint8), "RGBA")


def _robust_cell_color(cell: np.ndarray) -> np.ndarray:
    """Average the half of cell pixels closest to the cell median color."""
    if len(cell) <= 4:
        return cell.mean(axis=0)
    median = np.median(cell, axis=0)
    distances = np.linalg.norm(cell[:, :3] - median[:3], axis=1)
    keep = distances.argsort()[: max(len(cell) // 2, 1)]
    return cell[keep].mean(axis=0)
