"""Broken clusters: tiny per-color islands that border other opaque colors (D-013).

Distinct from floating pixels (which are surrounded by transparency): these are small color specks
*inside* the sprite body — the residue of noisy dithering or quantization. The safe repair merges
them into the dominant neighbouring color.
"""

from __future__ import annotations

from collections import Counter

import numpy as np

from pixelforge.core.scene_graph import Finding, FindingSeverity
from pixelforge.qa.detectors.base import Detector, opaque_mask
from pixelforge.qa.regions import label_components, region_of

_MAX_FINDINGS = 25
_NEIGHBORS_4 = ((-1, 0), (1, 0), (0, -1), (0, 1))


def _has_external_opaque_neighbor(comp: np.ndarray, opaque: np.ndarray) -> bool:
    external = opaque & ~comp
    up = np.zeros_like(comp)
    up[:-1, :] = external[1:, :]
    down = np.zeros_like(comp)
    down[1:, :] = external[:-1, :]
    left = np.zeros_like(comp)
    left[:, :-1] = external[:, 1:]
    right = np.zeros_like(comp)
    right[:, 1:] = external[:, :-1]
    return bool((comp & (up | down | left | right)).any())


def _broken_components(rgba: np.ndarray, min_size: int) -> list[np.ndarray]:
    opaque = opaque_mask(rgba)
    if not opaque.any():
        return []
    rgb = rgba[..., :3]
    components: list[np.ndarray] = []
    for color in np.unique(rgb[opaque], axis=0):
        color_mask = opaque & np.all(rgb == color, axis=-1)
        count, labels = label_components(color_mask, connectivity=4)
        for label in range(1, count + 1):
            comp = labels == label
            if int(comp.sum()) < min_size and _has_external_opaque_neighbor(comp, opaque):
                components.append(comp)
    return components


class BrokenClustersDetector(Detector):
    name = "broken-cluster"
    repairable = True

    def detect(self, rgba: np.ndarray, context) -> list[Finding]:
        components = _broken_components(rgba, context.min_cluster_size)
        findings: list[Finding] = []
        for comp in components[:_MAX_FINDINGS]:
            ys, xs = np.nonzero(comp)
            findings.append(
                Finding(
                    detector=self.name,
                    severity=FindingSeverity.WARNING,
                    message=f"broken cluster ({int(comp.sum())} px) smaller than "
                    f"{context.min_cluster_size}",
                    region=region_of(ys, xs),
                )
            )
        if len(components) > _MAX_FINDINGS:
            findings.append(
                Finding(
                    detector=self.name,
                    severity=FindingSeverity.WARNING,
                    message=f"...and {len(components) - _MAX_FINDINGS} more broken clusters",
                )
            )
        return findings

    def repair(self, rgba: np.ndarray, context) -> np.ndarray:
        out = rgba.copy()
        components = _broken_components(rgba, context.min_cluster_size)
        if not components:
            return out
        broken = np.zeros(rgba.shape[:2], dtype=bool)
        for comp in components:
            broken |= comp
        opaque = opaque_mask(rgba)
        height, width = rgba.shape[:2]
        coords = np.nonzero(broken)
        for y, x in zip(coords[0].tolist(), coords[1].tolist(), strict=True):
            candidates = [
                tuple(int(v) for v in rgba[y + dy, x + dx, :3])
                for dy, dx in _NEIGHBORS_4
                if 0 <= y + dy < height
                and 0 <= x + dx < width
                and opaque[y + dy, x + dx]
                and not broken[y + dy, x + dx]
            ]
            if candidates:
                out[y, x, :3] = Counter(candidates).most_common(1)[0][0]
                out[y, x, 3] = 255
        return out
