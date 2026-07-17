"""Connected-component labeling for QA detectors (no scipy dependency)."""

from __future__ import annotations

import numpy as np

from pixelforge.core.scene_graph import Region

_OFFSETS_4 = ((-1, 0), (1, 0), (0, -1), (0, 1))
_OFFSETS_8 = ((-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1))


def label_components(mask: np.ndarray, connectivity: int = 4) -> tuple[int, np.ndarray]:
    """Label connected ``True`` regions of a boolean mask via iterative flood fill.

    Returns ``(count, labels)``; ``labels`` is an int array (0 = background, 1..count = regions).
    """
    height, width = mask.shape
    labels = np.zeros((height, width), dtype=np.int32)
    offsets = _OFFSETS_8 if connectivity == 8 else _OFFSETS_4
    count = 0
    ys, xs = np.nonzero(mask)
    for start_y, start_x in zip(ys.tolist(), xs.tolist(), strict=True):
        if labels[start_y, start_x] != 0:
            continue
        count += 1
        stack = [(start_y, start_x)]
        labels[start_y, start_x] = count
        while stack:
            cy, cx = stack.pop()
            for dy, dx in offsets:
                ny, nx = cy + dy, cx + dx
                if 0 <= ny < height and 0 <= nx < width and mask[ny, nx] and labels[ny, nx] == 0:
                    labels[ny, nx] = count
                    stack.append((ny, nx))
    return count, labels


def region_of(ys: np.ndarray, xs: np.ndarray) -> Region:
    """Bounding-box :class:`Region` of a set of pixel coordinates."""
    y0, x0 = int(ys.min()), int(xs.min())
    return Region(x=x0, y=y0, width=int(xs.max()) - x0 + 1, height=int(ys.max()) - y0 + 1)
