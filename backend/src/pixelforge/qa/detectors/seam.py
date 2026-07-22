"""Seam-discontinuity detector (M22, D-013, advise-only).

Only fires for sprites meant to tile (``context.tileable``). It measures the edge-wrap difference —
how far the left/right and top/bottom edges are from matching — and warns when a visible seam would
show up on repeat. Deterministic; reuses ``generation.tileize.seam_metrics``.
"""

from __future__ import annotations

import numpy as np

from pixelforge.core.scene_graph import Finding, FindingSeverity, Region
from pixelforge.generation.tileize import seam_metrics
from pixelforge.qa.detectors.base import Detector
from pixelforge.qa.models import DetectorContext

_WARN = 0.08  # mean per-channel edge difference (of 1.0) above this reads as a visible seam
_INFO = 0.02


class SeamDiscontinuityDetector(Detector):
    name = "seam-discontinuity"

    def detect(self, rgba: np.ndarray, context: DetectorContext) -> list[Finding]:
        if not context.tileable:
            return []
        height, width = rgba.shape[:2]
        horizontal, vertical = seam_metrics(rgba)
        findings: list[Finding] = []
        if horizontal > _INFO:
            findings.append(
                self._finding(horizontal, "left/right", Region(x=0, y=0, width=1, height=height))
            )
        if vertical > _INFO:
            findings.append(
                self._finding(vertical, "top/bottom", Region(x=0, y=0, width=width, height=1))
            )
        return findings

    def _finding(self, diff: float, edges: str, region: Region) -> Finding:
        severity = FindingSeverity.WARNING if diff > _WARN else FindingSeverity.INFO
        return Finding(
            detector=self.name,
            severity=severity,
            message=f"{edges} edges differ by {diff * 100:.1f}% — visible seam when tiled",
            region=region,
        )
