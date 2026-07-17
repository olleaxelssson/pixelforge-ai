"""Pillow shading: light appears to come from everywhere (bright center, dark all edges) (D-013)."""

from __future__ import annotations

import numpy as np

from pixelforge.core.scene_graph import Finding, FindingSeverity, Region
from pixelforge.qa.detectors.base import Detector
from pixelforge.qa.shading import opaque_luminance, pearson

_MIN_PIXELS = 16
_RADIAL_THRESHOLD = 0.55
_DIRECTIONAL_THRESHOLD = 0.35


class PillowShadingDetector(Detector):
    name = "pillow-shading"

    def detect(self, rgba: np.ndarray, context) -> list[Finding]:
        lum, ys, xs = opaque_luminance(rgba)
        if len(lum) < _MIN_PIXELS:
            return []
        dy = ys - ys.mean()
        dx = xs - xs.mean()
        distance = np.sqrt(dy**2 + dx**2)

        radial = -pearson(lum, distance)  # >0 when the center is brighter than the edges
        directional = float(np.hypot(pearson(lum, dx), pearson(lum, dy)))

        if radial > _RADIAL_THRESHOLD and directional < _DIRECTIONAL_THRESHOLD:
            height, width = rgba.shape[:2]
            return [
                Finding(
                    detector=self.name,
                    severity=FindingSeverity.WARNING,
                    message="pillow shading: brightness radiates from the center with no light "
                    "direction",
                    region=Region(x=0, y=0, width=width, height=height),
                )
            ]
        return []
