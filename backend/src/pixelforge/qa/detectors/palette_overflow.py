"""Palette overflow: more unique colors than the budget allows (D-013)."""

from __future__ import annotations

import numpy as np
from PIL import Image

from pixelforge.core.scene_graph import Finding, FindingSeverity, Region
from pixelforge.palettes.quantize import apply_palette, extract_palette
from pixelforge.qa.detectors.base import Detector, opaque_mask


class PaletteOverflowDetector(Detector):
    name = "palette-overflow"
    repairable = True

    def _budget(self, context) -> int:
        return len(context.palette) if context.palette else context.max_colors

    def _unique_colors(self, rgba: np.ndarray) -> np.ndarray:
        rgb = rgba[opaque_mask(rgba)][:, :3]
        return np.unique(rgb, axis=0) if len(rgb) else rgb

    def detect(self, rgba: np.ndarray, context) -> list[Finding]:
        budget = self._budget(context)
        count = len(self._unique_colors(rgba))
        if count <= budget:
            return []
        height, width = rgba.shape[:2]
        return [
            Finding(
                detector=self.name,
                severity=FindingSeverity.WARNING,
                message=f"palette overflow: {count} colors exceed the {budget}-color budget",
                region=Region(x=0, y=0, width=width, height=height),
            )
        ]

    def repair(self, rgba: np.ndarray, context) -> np.ndarray:
        budget = self._budget(context)
        image = Image.fromarray(rgba, "RGBA")
        colors = context.palette or extract_palette(image, budget)
        return np.asarray(apply_palette(image, colors), dtype=np.uint8)
