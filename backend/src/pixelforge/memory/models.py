"""Character-memory data models (D-011).

The identity is expressed as a Scene-Graph fragment (reused verbatim on every generation), which is
what structurally defeats drift — the parts/materials/palette that define the character are data,
not a re-interpreted prompt.
"""

from __future__ import annotations

import time
import uuid

from pydantic import BaseModel, Field

from pixelforge.core.scene_graph import EntityKind, Material, Part


class CharacterIdentity(BaseModel):
    """The reusable identity slots — held fixed across a character's generations."""

    subject: str  # e.g. "Captain Elias, a grizzled veteran knight"
    kind: EntityKind = EntityKind.CHARACTER
    parts: list[Part] = Field(default_factory=list)  # body / face / hair / signature equipment
    materials: list[Material] = Field(default_factory=list)
    proportions: str = ""  # e.g. "tall, broad-shouldered"
    silhouette: str = ""  # e.g. "horned helm, long cape"
    bible: str = ""  # freeform canon / personality notes


class ReferenceFrame(BaseModel):
    filename: str
    label: str = "variant"  # "passport" for the canonical reference


class Character(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    name: str
    identity: CharacterIdentity
    palette_id: str | None = None
    reference_frames: list[ReferenceFrame] = Field(default_factory=list)
    embedding: list[float] = Field(default_factory=list)  # canonical identity embedding
    embedding_backend: str = "mock"
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)

    def canonical_frame(self) -> ReferenceFrame | None:
        for frame in self.reference_frames:
            if frame.label == "passport":
                return frame
        return self.reference_frames[0] if self.reference_frames else None


class DriftResult(BaseModel):
    character_id: str
    similarity: float
    threshold: float
    consistent: bool
