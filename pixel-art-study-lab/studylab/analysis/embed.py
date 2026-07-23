"""Local visual embedding for semantic similarity search — no ML dependencies.

We hand-build a descriptor that captures what makes two pixel-art images "look alike":
- **structure**: a 16×16 grayscale thumbnail (silhouette / layout),
- **colour**: a coarse HSV histogram (palette feel),
- **linework**: a gradient-orientation histogram,
- **shape scalars**: palette size, aspect ratio, coverage, dithering.

L2-normalised, so cosine similarity ranks visually similar references. It is deterministic and runs
instantly on a CPU. (An optional API vision model can add semantics on top — see ``vlm.py``.)
"""

from __future__ import annotations

import numpy as np

EMBED_DIM = 16 * 16 + 8 * 3 * 3 + 8 + 4  # 340


def _block_resize_gray(gray: np.ndarray, size: int) -> np.ndarray:
    """Area-average downscale of a 2-D array to ``size×size`` (no PIL, deterministic)."""
    h, w = gray.shape
    ys = (np.linspace(0, h, size + 1)).astype(int)
    xs = (np.linspace(0, w, size + 1)).astype(int)
    out = np.zeros((size, size), dtype=np.float64)
    for i in range(size):
        for j in range(size):
            block = gray[max(ys[i], 0) : max(ys[i + 1], ys[i] + 1), xs[j] : max(xs[j + 1], xs[j] + 1)]
            out[i, j] = block.mean() if block.size else 0.0
    return out


def _rgb_to_hsv(rgb: np.ndarray) -> np.ndarray:
    r, g, b = (rgb[..., i] / 255.0 for i in range(3))
    mx = np.maximum.reduce([r, g, b])
    mn = np.minimum.reduce([r, g, b])
    d = mx - mn
    h = np.zeros_like(mx)
    mask = d > 1e-6
    idx = (mx == r) & mask
    h[idx] = ((g[idx] - b[idx]) / d[idx]) % 6
    idx = (mx == g) & mask
    h[idx] = (b[idx] - r[idx]) / d[idx] + 2
    idx = (mx == b) & mask
    h[idx] = (r[idx] - g[idx]) / d[idx] + 4
    h = (h / 6.0) % 1.0
    s = np.where(mx > 1e-6, d / np.maximum(mx, 1e-6), 0.0)
    return np.stack([h, s, mx], axis=-1)


def embed(rgba: np.ndarray) -> np.ndarray:
    """Return a float32 L2-normalised descriptor of shape ``(EMBED_DIM,)``."""
    rgb = rgba[..., :3].astype(np.float64)
    alpha = rgba[..., 3]
    opaque = alpha > 0

    gray = rgb.mean(axis=-1)
    gray = np.where(opaque, gray, 0.0)
    structure = (_block_resize_gray(gray, 16) / 255.0).flatten()

    # HSV histogram over opaque pixels (8 hue × 3 sat × 3 val).
    hist = np.zeros(8 * 3 * 3, dtype=np.float64)
    if opaque.any():
        hsv = _rgb_to_hsv(rgb[opaque])
        hb = np.clip((hsv[:, 0] * 8).astype(int), 0, 7)
        sb = np.clip((hsv[:, 1] * 3).astype(int), 0, 2)
        vb = np.clip((hsv[:, 2] * 3).astype(int), 0, 2)
        flat = hb * 9 + sb * 3 + vb
        for f in flat:
            hist[f] += 1
        hist /= hist.sum()

    # Gradient-orientation histogram on a 32×32 grayscale.
    g32 = _block_resize_gray(gray, 32)
    gx = np.zeros_like(g32)
    gy = np.zeros_like(g32)
    gx[:, 1:] = g32[:, 1:] - g32[:, :-1]
    gy[1:, :] = g32[1:, :] - g32[:-1, :]
    mag = np.sqrt(gx**2 + gy**2)
    ang = (np.arctan2(gy, gx) + np.pi) / (2 * np.pi)  # 0..1
    grad = np.zeros(8, dtype=np.float64)
    bins = np.clip((ang * 8).astype(int), 0, 7)
    for b in range(8):
        grad[b] = mag[bins == b].sum()
    if grad.sum() > 0:
        grad /= grad.sum()

    color_count = len(np.unique(rgb[opaque].astype(np.uint8), axis=0)) if opaque.any() else 0
    aspect = rgba.shape[1] / rgba.shape[0] if rgba.shape[0] else 1.0
    coverage = float(opaque.mean())
    scalars = np.array(
        [
            np.clip(color_count / 64.0, 0, 1),
            np.clip(aspect / 3.0, 0, 1),
            coverage,
            0.0,  # reserved (dithering filled by orchestrator if desired)
        ],
        dtype=np.float64,
    )

    vec = np.concatenate(
        [structure * 1.0, hist * 1.2, grad * 0.6, scalars * 0.5]
    ).astype(np.float32)
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    return vec


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b))  # inputs are already L2-normalised
