"""The Scene Graph: the typed, structured representation of one generation (D-009).

The Scene Graph is the single source of truth for what is being drawn. It is seeded by the Intent
agent, elaborated by planning agents, compiled into a ``DiffusionSpec``, annotated by QA, edited in
the UI, and persisted with the project. Colors are referenced as *palette indices*, never raw RGB —
RGB is resolved only at compile time from the referenced palette.

Serialization is canonical (sorted keys) so a Scene Graph hashes deterministically; the content hash
(which excludes volatile provenance) gives equivalent plans a stable identity for caching.

The schema is versioned. Load older project files through :func:`scene_graph_from_dict`, which runs
migrations; ``schema_version`` is bumped and a ``migrate`` step added whenever the shape changes.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

SCENE_GRAPH_SCHEMA_VERSION = 1


class EntityKind(str, Enum):
    CHARACTER = "character"
    CREATURE = "creature"
    ITEM = "item"
    WEAPON = "weapon"
    ARMOR = "armor"
    ENVIRONMENT = "environment"
    TILE = "tile"
    ICON = "icon"
    UI = "ui"
    PORTRAIT = "portrait"
    BACKGROUND = "background"
    GENERIC = "generic"


class CameraPerspective(str, Enum):
    FRONT = "front"
    SIDE = "side"
    THREE_QUARTER = "three-quarter"
    TOP_DOWN = "top-down"
    ISOMETRIC = "isometric"


class MaterialKind(str, Enum):
    METAL = "metal"
    CLOTH = "cloth"
    LEATHER = "leather"
    SKIN = "skin"
    WOOD = "wood"
    STONE = "stone"
    GEM = "gem"
    ENERGY = "energy"
    ORGANIC = "organic"
    GENERIC = "generic"


class Material(BaseModel):
    """A surface with a characteristic shading behavior (metal reflects, cloth is matte, ...)."""

    name: str
    kind: MaterialKind = MaterialKind.GENERIC
    description: str = ""


class Part(BaseModel):
    """A named region of the entity, drawn back-to-front by ``z_order``."""

    name: str
    description: str = ""
    z_order: int = 0
    material: str | None = None  # references Material.name
    palette_index_refs: list[int] = Field(default_factory=list)


class Entity(BaseModel):
    kind: EntityKind = EntityKind.GENERIC
    subject: str
    intent: str = ""
    parts: list[Part] = Field(default_factory=list)
    materials: list[Material] = Field(default_factory=list)


class PalettePlan(BaseModel):
    palette_id: str | None = None
    max_colors: int = Field(default=16, ge=2, le=256)
    locked: bool = False


class Lighting(BaseModel):
    direction: str = "top-left"
    intensity: float = Field(default=0.6, ge=0.0, le=1.0)
    single_source: bool = True


class Pose(BaseModel):
    description: str = "neutral standing pose"
    orientation: str = "front"


class Camera(BaseModel):
    perspective: CameraPerspective = CameraPerspective.FRONT
    framing: str = "centered"


class AnimationState(BaseModel):
    action: str = "idle"
    frame: int = 0
    direction: str = "south"


class Constraints(BaseModel):
    width: int = Field(default=32, ge=8, le=512)
    height: int = Field(default=32, ge=8, le=512)
    transparent_background: bool = True
    max_colors: int = Field(default=16, ge=2, le=256)
    dither: str = "none"
    outline: bool = True
    no_antialias: bool = True
    no_subpixel: bool = True


class FindingSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class Region(BaseModel):
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0


class Finding(BaseModel):
    """A QA observation written by the Pixel QA engine (D-013); empty until that milestone lands."""

    detector: str
    severity: FindingSeverity = FindingSeverity.WARNING
    message: str = ""
    region: Region | None = None


class Provenance(BaseModel):
    """Everything needed to re-derive or audit a generation."""

    user_prompt: str = ""
    expanded_prompt: str = ""
    negative_prompt: str = ""
    seed: int | None = None
    mode: str = ""
    style: str = ""
    planning_backend: str = ""
    agent_trace: list[str] = Field(default_factory=list)
    model_versions: dict[str, str] = Field(default_factory=dict)


class SceneGraph(BaseModel):
    schema_version: int = SCENE_GRAPH_SCHEMA_VERSION
    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    entity: Entity
    palette: PalettePlan = Field(default_factory=PalettePlan)
    lighting: Lighting = Field(default_factory=Lighting)
    pose: Pose = Field(default_factory=Pose)
    camera: Camera = Field(default_factory=Camera)
    animation: AnimationState | None = None
    constraints: Constraints = Field(default_factory=Constraints)
    qa: list[Finding] = Field(default_factory=list)
    provenance: Provenance = Field(default_factory=Provenance)
    tags: list[str] = Field(default_factory=list)

    def canonical_dict(self) -> dict[str, Any]:
        """JSON-compatible dict (enums as values) — the basis for stable serialization."""
        return self.model_dump(mode="json")

    def canonical_json(self) -> str:
        """Deterministic serialization: sorted keys, compact separators."""
        return json.dumps(self.canonical_dict(), sort_keys=True, separators=(",", ":"))

    def content_hash(self) -> str:
        """SHA-256 of the plan's *semantics* — excluding the instance ``id`` and volatile
        ``provenance`` — so two equivalent plans share an identity (used for dedup/caching)."""
        data = self.canonical_dict()
        data.pop("provenance", None)
        data.pop("id", None)
        blob = json.dumps(data, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def migrate_scene_graph(data: dict[str, Any]) -> dict[str, Any]:
    """Upgrade a serialized Scene Graph to the current schema version.

    v1 is the initial schema, so there is nothing to migrate yet; the loop is the extension point
    for future versions. A newer-than-supported version is a hard error rather than a silent guess.
    """
    version = int(data.get("schema_version", SCENE_GRAPH_SCHEMA_VERSION))
    if version > SCENE_GRAPH_SCHEMA_VERSION:
        raise ValueError(
            f"scene graph schema_version {version} is newer than supported "
            f"{SCENE_GRAPH_SCHEMA_VERSION}; upgrade PixelForge to load this project"
        )
    # while version < SCENE_GRAPH_SCHEMA_VERSION: data = _migrate_v{version}(data); version += 1
    return data


def scene_graph_from_dict(data: dict[str, Any]) -> SceneGraph:
    """Load a Scene Graph from a (possibly older) serialized dict, running migrations."""
    return SceneGraph.model_validate(migrate_scene_graph(dict(data)))


def scene_graph_json_schema() -> dict[str, Any]:
    """The JSON Schema for the Scene Graph — the source the frontend mirrors for its TS types."""
    return SceneGraph.model_json_schema()
