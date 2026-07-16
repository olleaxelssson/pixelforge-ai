"""Compile a Scene Graph into diffusion prompts (D-009).

This is the bridge from the structured plan to Stage A. It replaces the ad-hoc string concatenation
of ``prompt_builder`` when the planning layer is active, deriving the prompt from the entity, its
parts, the camera/pose, lighting, and constraints — so every phrase traces back to a plan decision.
``prompt_builder`` remains the fast path when planning is disabled.
"""

from __future__ import annotations

from pixelforge.core.scene_graph import CameraPerspective, EntityKind, SceneGraph
from pixelforge.styles.model import StylePreset

_KIND_PHRASE: dict[EntityKind, str] = {
    EntityKind.CHARACTER: "full-body game character sprite of",
    EntityKind.CREATURE: "game creature sprite of",
    EntityKind.ITEM: "game item icon of",
    EntityKind.WEAPON: "game weapon sprite of",
    EntityKind.ARMOR: "game armor equipment sprite of",
    EntityKind.ENVIRONMENT: "game environment scene of",
    EntityKind.TILE: "seamless tileable game texture tile of",
    EntityKind.ICON: "game skill icon of",
    EntityKind.UI: "game UI element",
    EntityKind.PORTRAIT: "pixel art portrait of",
    EntityKind.BACKGROUND: "game background of",
    EntityKind.GENERIC: "",
}

_CAMERA_PHRASE: dict[CameraPerspective, str] = {
    CameraPerspective.FRONT: "front view",
    CameraPerspective.SIDE: "side view",
    CameraPerspective.THREE_QUARTER: "three-quarter view",
    CameraPerspective.TOP_DOWN: "top-down view",
    CameraPerspective.ISOMETRIC: "isometric view",
}

_PIXEL_ART_NEGATIVES = [
    "blurry",
    "anti-aliased",
    "soft gradient",
    "jpeg artifacts",
    "subpixel rendering",
    "photorealistic",
]

_CHARACTER_KINDS = {EntityKind.CHARACTER, EntityKind.CREATURE}


def compile_prompt(scene_graph: SceneGraph, style: StylePreset | None = None) -> str:
    entity = scene_graph.entity
    parts: list[str] = []
    if style is not None and style.prompt_prefix:
        parts.append(style.prompt_prefix)

    kind_phrase = _KIND_PHRASE.get(entity.kind, "")
    parts.append(f"{kind_phrase} {entity.subject}".strip() if kind_phrase else entity.subject)

    named_parts = [p.name for p in entity.parts if p.name != "body"]
    if named_parts:
        parts.append("with " + ", ".join(named_parts))

    parts.append(_CAMERA_PHRASE[scene_graph.camera.perspective])

    if entity.kind in _CHARACTER_KINDS and scene_graph.pose.description:
        parts.append(scene_graph.pose.description)

    if scene_graph.lighting.direction and scene_graph.lighting.direction != "none":
        parts.append(f"light source from {scene_graph.lighting.direction}")

    if scene_graph.constraints.transparent_background:
        parts.append("isolated on plain solid background")

    if style is not None and style.prompt_suffix:
        parts.append(style.prompt_suffix)

    return ", ".join(part.strip().strip(",") for part in parts if part and part.strip())


def compile_negative_prompt(scene_graph: SceneGraph, style: StylePreset | None = None) -> str:
    sources = list(_PIXEL_ART_NEGATIVES)
    if scene_graph.provenance.negative_prompt:
        sources.append(scene_graph.provenance.negative_prompt)
    if style is not None and style.negative_prompt:
        sources.append(style.negative_prompt)

    # Sources may be comma-joined strings; split and dedupe per term (case-insensitive, order-kept).
    seen: set[str] = set()
    ordered: list[str] = []
    for source in sources:
        for term in source.split(","):
            text = term.strip()
            if text and text.lower() not in seen:
                seen.add(text.lower())
                ordered.append(text)
    return ", ".join(ordered)
