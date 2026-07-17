"""Lighting planner: refine the Art Director's light into a final plan (D-010, M11).

Keeps the single-source discipline, boosts intensity for dramatic styles, and turns on rim light
when glowing/energy materials are present. Depends on the Intent agent and the Art Director.
"""

from __future__ import annotations

from pydantic import BaseModel

from pixelforge.agents.art_director import ArtDirectionResult
from pixelforge.agents.base import Agent, PlanningContext
from pixelforge.agents.intent import IntentResult
from pixelforge.agents.planning_backends.base import AgentCall
from pixelforge.core.scene_graph import Lighting, MaterialKind


class LightingPlanResult(BaseModel):
    lighting: Lighting


def build_lighting_plan(context: PlanningContext) -> LightingPlanResult:
    """Deterministic lighting refinement — the mock backend's response and offline fast planner."""
    intent = context.output("intent", IntentResult)
    art = context.output("art-director", ArtDirectionResult)
    lighting = art.lighting.model_copy(deep=True)
    lighting.single_source = True  # pixel-art discipline: one readable key light

    has_energy = any(m.kind is MaterialKind.ENERGY for m in intent.entity.materials)
    if has_energy:
        lighting.rim_light = True
        lighting.intensity = max(lighting.intensity, 0.7)
    return LightingPlanResult(lighting=lighting)


class LightingAgent(Agent):
    name = "lighting"
    output_model = LightingPlanResult
    dependencies: tuple[str, ...] = ("intent", "art-director")

    def build_call(self, context: PlanningContext) -> AgentCall:
        return AgentCall(
            agent=self.name,
            deterministic=build_lighting_plan(context),
            system="You are a lighting-planning agent for a pixel-art generator.",
            instructions=(
                "Refine the art direction into a final single-source lighting plan; enable rim "
                "light only when glowing materials warrant it. Respond as structured JSON."
            ),
            context={"shading_style": context.request.shading_style},
        )
