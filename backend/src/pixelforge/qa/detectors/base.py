"""Detector interface: inspect an RGBA sprite, emit findings, optionally auto-repair (D-013)."""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np

from pixelforge.core.scene_graph import Finding
from pixelforge.qa.models import DetectorContext


class Detector(ABC):
    name: str = "abstract"
    #: Whether this detector can deterministically fix what it finds without touching good pixels.
    repairable: bool = False

    @abstractmethod
    def detect(self, rgba: np.ndarray, context: DetectorContext) -> list[Finding]:
        """Return findings for an ``(H, W, 4)`` uint8 RGBA array."""

    def repair(self, rgba: np.ndarray, context: DetectorContext) -> np.ndarray:
        """Return a repaired copy of ``rgba``. Default: no-op (advise-only detectors)."""
        return rgba


def opaque_mask(rgba: np.ndarray) -> np.ndarray:
    """Boolean mask of non-transparent pixels."""
    return rgba[..., 3] > 0
