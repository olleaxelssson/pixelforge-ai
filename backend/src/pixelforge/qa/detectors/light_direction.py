"""Light-direction consistency: shading gradient vs. the intended light source (D-013).

Context-gated: only runs when the plan specifies a lighting direction. Image coordinates are y-down,
so "top-left" light means brightness should increase toward (-x, -y).
"""

from __future__ import annotations

import numpy as np

from pixelforge.core.scene_graph import Finding, FindingSeverity, Region
from pixelforge.qa.detectors.base import Detector
from pixelforge.qa.shading import opaque_luminance, pearson

_MIN_PIXELS = 16
_MIN_STRENGTH = 0.2
_OPPOSITE_DOT = -0.2

_DIRECTIONS: dict[str, tuple[float, float]] = {
    "top-left": (-1.0, -1.0),
    "top": (0.0, -1.0),
    "top-right": (1.0, -1.0),
    "left": (-1.0, 0.0),
    "right": (1.0, 0.0),
    "bottom-left": (-1.0, 1.0),
    "bottom": (0.0, 1.0),
    "bottom-right": (1.0, 1.0),
}


def _normalize(vx: float, vy: float) -> tuple[float, float]:
    magnitude = float(np.hypot(vx, vy))
    return (vx / magnitude, vy / magnitude) if magnitude > 0 else (0.0, 0.0)


class LightDirectionDetector(Detector):
    name = "light-direction"

    def detect(self, rgba: np.ndarray, context) -> list[Finding]:
        direction = context.lighting_direction
        if not direction or direction == "none":
            return []
        expected = _DIRECTIONS.get(direction)
        if expected is None:
            return []

        lum, ys, xs = opaque_luminance(rgba)
        if len(lum) < _MIN_PIXELS:
            return []
        grad_x = pearson(lum, xs - xs.mean())
        grad_y = pearson(lum, ys - ys.mean())
        if float(np.hypot(grad_x, grad_y)) < _MIN_STRENGTH:
            return []  # too flat to judge

        gx, gy = _normalize(grad_x, grad_y)
        ex, ey = _normalize(*expected)
        if gx * ex + gy * ey < _OPPOSITE_DOT:
            height, width = rgba.shape[:2]
            return [
                Finding(
                    detector=self.name,
                    severity=FindingSeverity.WARNING,
                    message=f"shading runs opposite to the intended {direction} light source",
                    region=Region(x=0, y=0, width=width, height=height),
                )
            ]
        return []
