"""QA data models: detector context, scores, and the report (D-013)."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, Field

from pixelforge.core.scene_graph import Finding
from pixelforge.palettes.model import RGB


@dataclass
class DetectorContext:
    """What the sprite is meant to be — lets detectors judge against intent, not just pixels."""

    max_colors: int = 16
    transparent_background: bool = True
    palette: list[RGB] | None = None  # locked palette colors, if any
    lighting_direction: str | None = None  # e.g. "top-left"; None disables the light-dir check
    min_cluster_size: int = 3


class QAScores(BaseModel):
    readability: float = 0.0
    palette: float = 0.0
    contrast: float = 0.0
    silhouette: float = 0.0
    cleanliness: float = 0.0
    overall: float = 0.0


class QAReport(BaseModel):
    width: int
    height: int
    passed: bool
    scores: QAScores
    findings: list[Finding] = Field(default_factory=list)
