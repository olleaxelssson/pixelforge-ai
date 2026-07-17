"""Shared brightness-structure helpers for the shading detectors (D-013)."""

from __future__ import annotations

import numpy as np


def opaque_luminance(rgba: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return (luminance, y, x) over opaque pixels (Rec.601 luma is enough for structure)."""
    opaque = rgba[..., 3] > 0
    ys, xs = np.nonzero(opaque)
    rgb = rgba[opaque][:, :3].astype(np.float64)
    lum = 0.299 * rgb[:, 0] + 0.587 * rgb[:, 1] + 0.114 * rgb[:, 2]
    return lum, ys.astype(np.float64), xs.astype(np.float64)


def pearson(a: np.ndarray, b: np.ndarray) -> float:
    """Pearson correlation of two 1-D arrays; 0 when either is constant."""
    a = a - a.mean()
    b = b - b.mean()
    denom = float(np.sqrt((a * a).sum() * (b * b).sum()))
    return float((a * b).sum() / denom) if denom > 0 else 0.0
