"""Material planner: per-material finish hints (D-010, M11).

Fills each material's finish slots — specular pixels, whether dithering is acceptable on the
surface, and the shading-ramp length. Depends on the Intent agent.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from pixelforge.agents.base import Agent, PlanningContext
from pixelforge.agents.intent import IntentResult
from pixelforge.agents.planning_backends.base import AgentCall
from pixelforge.core.scene_graph import Material, MaterialKind

# kind → (specular, dither_ok, ramp_size). Metal/gem get sharp highlights and clean ramps;
# energy glows without dithering; organic/cloth surfaces tolerate dithered texture.
_FINISH: dict[MaterialKind, tuple[bool, bool, int]] = {
    MaterialKind.METAL: (True, False, 4),
    MaterialKind.GEM: (True, False, 4),
    MaterialKind.ENERGY: (True, False, 2),
    MaterialKind.CLOTH: (False, True, 3),
    MaterialKind.LEATHER: (False, True, 3),
    MaterialKind.WOOD: (False, True, 3),
    MaterialKind.STONE: (False, True, 3),
    MaterialKind.ORGANIC: (False, True, 3),
    MaterialKind.SKIN: (False, False, 3),
    MaterialKind.GENERIC: (False, True, 3),
}


class MaterialPlanResult(BaseModel):
    materials: list[Material] = Field(default_factory=list)


def build_material_plan(context: PlanningContext) -> MaterialPlanResult:
    """Deterministic material finishes — the mock backend's response and offline fast planner."""
    intent = context.output("intent", IntentResult)
    planned: list[Material] = []
    for material in intent.entity.materials:
        specular, dither_ok, ramp = _FINISH[material.kind]
        planned.append(
            material.model_copy(
                update={"specular": specular, "dither_ok": dither_ok, "ramp_size": ramp}
            )
        )
    return MaterialPlanResult(materials=planned)


class MaterialAgent(Agent):
    name = "material"
    output_model = MaterialPlanResult
    dependencies: tuple[str, ...] = ("intent",)

    def build_call(self, context: PlanningContext) -> AgentCall:
        return AgentCall(
            agent=self.name,
            deterministic=build_material_plan(context),
            system="You are a material-planning agent for a pixel-art generator.",
            instructions=(
                "For each material, decide specular highlights, whether dithering is acceptable, "
                "and the shading-ramp length. Respond as structured JSON."
            ),
            context={
                "materials": [
                    m.kind.value for m in context.output("intent", IntentResult).entity.materials
                ]
            },
        )
