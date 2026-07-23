"""Palette analysis: colours, dominant colours, shading ramps, and a readability proxy."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

RGB = tuple[int, int, int]


def _luminance(c: RGB) -> float:
    r, g, b = c
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _hue(c: RGB) -> float:
    r, g, b = (v / 255.0 for v in c)
    mx, mn = max(r, g, b), min(r, g, b)
    if mx == mn:
        return -1.0  # achromatic
    d = mx - mn
    if mx == r:
        h = (g - b) / d % 6
    elif mx == g:
        h = (b - r) / d + 2
    else:
        h = (r - g) / d + 4
    return (h * 60.0) % 360.0


@dataclass
class PaletteAnalysis:
    color_count: int
    dominant: list[RGB]
    ramps: list[list[RGB]]
    contrast_range: float  # luminance spread of dominant colours, 0..1
    min_separation: float  # smallest RGB gap between dominant colours, 0..1 (higher = more legible)
    hex: list[str] = field(default_factory=list)


def _hexstr(c: RGB) -> str:
    return "#{:02x}{:02x}{:02x}".format(*c)


def analyze_palette(rgba: np.ndarray, max_dominant: int = 16) -> PaletteAnalysis:
    opaque = rgba[rgba[..., 3] > 0][:, :3]
    if len(opaque) == 0:
        return PaletteAnalysis(0, [], [], 0.0, 0.0, [])

    colors, counts = np.unique(opaque, axis=0, return_counts=True)
    order = np.argsort(counts)[::-1]
    dominant_arr = colors[order][:max_dominant]
    dominant: list[RGB] = [(int(c[0]), int(c[1]), int(c[2])) for c in dominant_arr]

    # Contrast: luminance spread across dominant colours (normalised to 0..1).
    lums = [_luminance(c) for c in dominant]
    contrast_range = (max(lums) - min(lums)) / 255.0 if len(lums) > 1 else 0.0

    # Readability proxy: smallest Euclidean RGB gap between any two dominant colours.
    min_sep = 1.0
    for i in range(len(dominant)):
        for j in range(i + 1, len(dominant)):
            d = float(np.linalg.norm(np.array(dominant[i]) - np.array(dominant[j]))) / 441.67
            min_sep = min(min_sep, d)
    if len(dominant) < 2:
        min_sep = 0.0

    return PaletteAnalysis(
        color_count=int(len(colors)),
        dominant=dominant,
        ramps=_build_ramps(dominant),
        contrast_range=round(contrast_range, 3),
        min_separation=round(min_sep, 3),
        hex=[_hexstr(c) for c in dominant],
    )


def _build_ramps(colors: list[RGB], bucket_deg: float = 40.0) -> list[list[RGB]]:
    """Group colours into shading ramps by hue bucket, each sorted dark→light."""
    buckets: dict[int, list[RGB]] = {}
    grays: list[RGB] = []
    for c in colors:
        h = _hue(c)
        if h < 0:
            grays.append(c)
        else:
            buckets.setdefault(int(h // bucket_deg), []).append(c)
    ramps = [sorted(v, key=_luminance) for v in buckets.values() if len(v) >= 2]
    if len(grays) >= 2:
        ramps.append(sorted(grays, key=_luminance))
    return sorted(ramps, key=len, reverse=True)
