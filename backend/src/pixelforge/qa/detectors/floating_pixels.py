"""Floating pixels: opaque pixels with no 4-connected opaque neighbor (D-013)."""

from __future__ import annotations

import numpy as np

from pixelforge.core.scene_graph import Finding, FindingSeverity, Region
from pixelforge.qa.detectors.base import Detector, opaque_mask

_MAX_FINDINGS = 25


def _floating(rgba: np.ndarray) -> np.ndarray:
    opaque = opaque_mask(rgba)
    padded = np.pad(opaque, 1, constant_values=False)
    neighbors = (
        padded[:-2, 1:-1].astype(np.uint8) + padded[2:, 1:-1] + padded[1:-1, :-2] + padded[1:-1, 2:]
    )
    return opaque & (neighbors == 0)


class FloatingPixelsDetector(Detector):
    name = "floating-pixel"
    repairable = True

    def detect(self, rgba: np.ndarray, context) -> list[Finding]:
        ys, xs = np.nonzero(_floating(rgba))
        findings: list[Finding] = []
        for y, x in zip(ys.tolist()[:_MAX_FINDINGS], xs.tolist()[:_MAX_FINDINGS], strict=True):
            findings.append(
                Finding(
                    detector=self.name,
                    severity=FindingSeverity.WARNING,
                    message=f"floating pixel at ({x}, {y})",
                    region=Region(x=x, y=y, width=1, height=1),
                )
            )
        if len(ys) > _MAX_FINDINGS:
            findings.append(
                Finding(
                    detector=self.name,
                    severity=FindingSeverity.WARNING,
                    message=f"...and {len(ys) - _MAX_FINDINGS} more floating pixels",
                )
            )
        return findings

    def repair(self, rgba: np.ndarray, context) -> np.ndarray:
        out = rgba.copy()
        out[_floating(rgba)] = 0
        return out
