"""Detector registry: the set of QA detectors, extended by adding entries (D-005/D-013).

Repairable detectors are listed first so the engine applies fixes in a sensible order
(remove floating pixels → merge broken clusters → snap the palette).
"""

from __future__ import annotations

from pixelforge.core.errors import UnknownRegistryKeyError
from pixelforge.qa.detectors.base import Detector
from pixelforge.qa.detectors.broken_clusters import BrokenClustersDetector
from pixelforge.qa.detectors.floating_pixels import FloatingPixelsDetector
from pixelforge.qa.detectors.light_direction import LightDirectionDetector
from pixelforge.qa.detectors.palette_overflow import PaletteOverflowDetector
from pixelforge.qa.detectors.pillow_shading import PillowShadingDetector
from pixelforge.qa.detectors.silhouette import SilhouetteDetector

BUILTIN_DETECTORS: list[Detector] = [
    FloatingPixelsDetector(),
    BrokenClustersDetector(),
    PaletteOverflowDetector(),
    SilhouetteDetector(),
    PillowShadingDetector(),
    LightDirectionDetector(),
]


class DetectorRegistry:
    def __init__(self, detectors: list[Detector] | None = None) -> None:
        chosen = detectors if detectors is not None else BUILTIN_DETECTORS
        self._detectors: dict[str, Detector] = {d.name: d for d in chosen}

    def list(self) -> list[Detector]:
        return list(self._detectors.values())

    def get(self, name: str) -> Detector:
        detector = self._detectors.get(name)
        if detector is None:
            raise UnknownRegistryKeyError(f"unknown detector: {name}")
        return detector
