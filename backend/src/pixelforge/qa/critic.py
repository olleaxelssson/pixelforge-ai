"""AI critic (D-013): scores a sprite's commercial quality.

M9 ships the deterministic :class:`HeuristicCritic`, reusing the palette intelligence from D-012
(readability, contrast) and the detector findings (cleanliness) — no VLM, runs in CI. A VLM-backed
critic can implement the same :class:`Critic` interface in a later milestone without other changes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np

from pixelforge.core.scene_graph import Finding, FindingSeverity
from pixelforge.palettes.analysis import analyze_palette
from pixelforge.palettes.model import Palette, rgb_to_hex
from pixelforge.qa.models import DetectorContext, QAScores

_COLOR_CAP = 64
_CLEAN_DETECTORS = {"floating-pixel", "broken-cluster", "palette-overflow"}


class Critic(ABC):
    @abstractmethod
    def score(
        self, rgba: np.ndarray, context: DetectorContext, findings: list[Finding]
    ) -> QAScores:
        """Score the sprite in [0, 1] on each axis plus an overall."""


def _dominant_colors(rgba: np.ndarray) -> tuple[list[str], int]:
    opaque = rgba[..., 3] > 0
    rgb = rgba[opaque][:, :3]
    if len(rgb) == 0:
        return [], 0
    colors, counts = np.unique(rgb, axis=0, return_counts=True)
    order = np.argsort(counts)[::-1][:_COLOR_CAP]
    hexes = [rgb_to_hex((int(c[0]), int(c[1]), int(c[2]))) for c in colors[order]]
    return hexes, len(colors)


class HeuristicCritic(Critic):
    def score(
        self, rgba: np.ndarray, context: DetectorContext, findings: list[Finding]
    ) -> QAScores:
        hexes, unique_count = _dominant_colors(rgba)
        coverage = float((rgba[..., 3] > 0).mean())
        if not hexes:
            return QAScores()  # empty sprite → all zeros

        analysis = analyze_palette(Palette(id="_qa", name="qa", colors=hexes))
        readability = analysis.readability_score
        contrast = min(analysis.contrast.max_contrast_ratio / 7.0, 1.0)

        budget = len(context.palette) if context.palette else context.max_colors
        overflow = max(0, unique_count - budget)
        palette = max(0.0, 1.0 - overflow / max(1, budget) - 0.05 * len(analysis.duplicates))

        if coverage < 0.03:
            silhouette = 0.1
        elif context.transparent_background and coverage > 0.9:
            silhouette = 0.5
        else:
            silhouette = 1.0

        defects = sum(
            1
            for f in findings
            if f.detector in _CLEAN_DETECTORS and f.severity != FindingSeverity.INFO
        )
        cleanliness = max(0.0, 1.0 - 0.1 * defects)

        overall = (
            0.25 * readability
            + 0.20 * palette
            + 0.20 * contrast
            + 0.15 * silhouette
            + 0.20 * cleanliness
        )
        return QAScores(
            readability=round(readability, 3),
            palette=round(palette, 3),
            contrast=round(contrast, 3),
            silhouette=round(silhouette, 3),
            cleanliness=round(cleanliness, 3),
            overall=round(overall, 3),
        )
