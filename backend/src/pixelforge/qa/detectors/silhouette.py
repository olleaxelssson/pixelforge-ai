"""Silhouette readability: coverage and framing of the sprite (D-013, advise-only)."""

from __future__ import annotations

import numpy as np

from pixelforge.core.scene_graph import Finding, FindingSeverity, Region
from pixelforge.qa.detectors.base import Detector, opaque_mask

_MIN_COVERAGE = 0.03
_FULL_COVERAGE = 0.9
_EDGE_COVERAGE = 0.6


class SilhouetteDetector(Detector):
    name = "silhouette"

    def detect(self, rgba: np.ndarray, context) -> list[Finding]:
        opaque = opaque_mask(rgba)
        height, width = opaque.shape
        coverage = float(opaque.mean())
        full = Region(x=0, y=0, width=width, height=height)
        findings: list[Finding] = []

        if coverage < _MIN_COVERAGE:
            findings.append(
                Finding(
                    detector=self.name,
                    severity=FindingSeverity.ERROR,
                    message=f"sprite is nearly empty ({coverage * 100:.1f}% opaque)",
                    region=full,
                )
            )
            return findings

        if context.transparent_background:
            if coverage > _FULL_COVERAGE:
                findings.append(
                    Finding(
                        detector=self.name,
                        severity=FindingSeverity.WARNING,
                        message="no clear silhouette: sprite fills the frame, little transparency",
                        region=full,
                    )
                )
            elif (
                coverage > _EDGE_COVERAGE
                and opaque[0, :].any()
                and opaque[-1, :].any()
                and opaque[:, 0].any()
                and opaque[:, -1].any()
            ):
                findings.append(
                    Finding(
                        detector=self.name,
                        severity=FindingSeverity.INFO,
                        message="silhouette touches all four frame edges (no margin)",
                        region=full,
                    )
                )
        return findings
