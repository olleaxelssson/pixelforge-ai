"""Art Director agent: decide palette, lighting, camera, and pose (D-010).

Runs after the Intent agent. It reads the parsed entity and turns the request + style defaults into
the artistic direction slots of the Scene Graph. Deterministic here; the same shape would come from
an LLM art-director prompt in a cloud backend.
"""

from __future__ import annotations

from pydantic import BaseModel

from pixelforge.agents.base import Agent, PlanningContext
from pixelforge.agents.intent import IntentResult
from pixelforge.agents.planning_backends.base import AgentCall
from pixelforge.core.scene_graph import (
    Camera,
    CameraPerspective,
    EntityKind,
    Lighting,
    PalettePlan,
    Pose,
)

_KIND_TO_PERSPECTIVE: dict[EntityKind, CameraPerspective] = {
    EntityKind.WEAPON: CameraPerspective.THREE_QUARTER,
    EntityKind.ENVIRONMENT: CameraPerspective.SIDE,
    EntityKind.BACKGROUND: CameraPerspective.SIDE,
    EntityKind.TILE: CameraPerspective.TOP_DOWN,
}

# Shading style → light intensity. Softer styles use a gentler key light.
_SHADING_INTENSITY: dict[str, float] = {
    "standard": 0.6,
    "soft": 0.4,
    "flat": 0.2,
    "dramatic": 0.85,
    "high-contrast": 0.9,
}


class ArtDirectionResult(BaseModel):
    palette: PalettePlan
    lighting: Lighting
    camera: Camera
    pose: Pose


def _palette_plan(context: PlanningContext) -> PalettePlan:
    request = context.request
    if request.palette_id:
        return PalettePlan(
            palette_id=request.palette_id, max_colors=request.max_colors, locked=True
        )
    style = context.style
    if style.default_palette_id:
        return PalettePlan(palette_id=style.default_palette_id, max_colors=request.max_colors)
    max_colors = min(request.max_colors, style.default_max_colors or request.max_colors)
    return PalettePlan(max_colors=max_colors)


def _lighting(context: PlanningContext) -> Lighting:
    request = context.request
    intensity = _SHADING_INTENSITY.get(request.shading_style, 0.6)
    return Lighting(direction=request.lighting_direction or "top-left", intensity=intensity)


def _pose(kind: EntityKind, mode_name: str) -> Pose:
    if kind in (EntityKind.CHARACTER, EntityKind.CREATURE):
        return Pose(description="neutral standing pose", orientation="front")
    return Pose(description="centered", orientation="front")


def build_art_direction(context: PlanningContext) -> ArtDirectionResult:
    """Deterministic art direction — the mock backend's response and the offline fast planner."""
    intent = context.output("intent", IntentResult)
    kind = intent.entity.kind
    perspective = _KIND_TO_PERSPECTIVE.get(kind, CameraPerspective.FRONT)
    return ArtDirectionResult(
        palette=_palette_plan(context),
        lighting=_lighting(context),
        camera=Camera(perspective=perspective),
        pose=_pose(kind, context.mode.name),
    )


class ArtDirectorAgent(Agent):
    name = "art-director"
    output_model = ArtDirectionResult
    dependencies: tuple[str, ...] = ("intent",)

    def build_call(self, context: PlanningContext) -> AgentCall:
        result = build_art_direction(context)
        return AgentCall(
            agent=self.name,
            deterministic=result,
            system="You are an art-director agent for a pixel-art generator.",
            instructions=(
                "Given the parsed entity, choose a palette plan, a single-source lighting setup, a "
                "camera perspective, and a pose. Respond as structured JSON."
            ),
            context={
                "style": context.style.id,
                "entity_kind": context.output("intent", IntentResult).entity.kind.value,
            },
        )
