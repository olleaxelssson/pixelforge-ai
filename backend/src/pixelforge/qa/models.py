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
    subject: str | None = None  # intended subject, e.g. "a knight" — enables the semantic critic
    tileable: bool = False  # sprite is meant to tile — enables the seam-discontinuity check (M22)


class QAScores(BaseModel):
    readability: float = 0.0
    palette: float = 0.0
    contrast: float = 0.0
    silhouette: float = 0.0
    cleanliness: float = 0.0
    overall: float = 0.0


class Critique(BaseModel):
    """Semantic/perceptual judgment from a critic backend (D-013 Layer 2).

    Beyond the pixel heuristics: does the sprite *read as* the intended subject, and does it appeal?
    ``subject_match``/``appeal`` are in [0, 1]; ``notes`` are short human-readable observations.
    """

    backend: str
    subject: str | None = None
    subject_match: float = 0.0
    appeal: float = 0.0
    verdict: str = ""
    notes: list[str] = Field(default_factory=list)


class QAReport(BaseModel):
    width: int
    height: int
    passed: bool
    scores: QAScores
    findings: list[Finding] = Field(default_factory=list)
    critique: Critique | None = None  # present when a semantic critic (VLM) is active
