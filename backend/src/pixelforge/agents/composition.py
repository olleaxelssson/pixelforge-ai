"""Composition planner: how the subject sits in the frame (D-010, M11).

Decides framing, margin, focal point, and refines the back-to-front draw order of parts. Depends on
the Intent agent (entity/parts) and the Art Director (camera).
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from pixelforge.agents.art_director import ArtDirectionResult
from pixelforge.agents.base import Agent, PlanningContext
from pixelforge.agents.intent import IntentResult
from pixelforge.agents.planning_backends.base import AgentCall
from pixelforge.core.scene_graph import Composition, EntityKind

_EDGE_TO_EDGE = {EntityKind.TILE, EntityKind.BACKGROUND, EntityKind.ENVIRONMENT, EntityKind.UI}
_TIGHT_MARGIN = {EntityKind.ICON, EntityKind.ITEM}

_FOCAL_POINTS: dict[EntityKind, str] = {
    EntityKind.CHARACTER: "upper third (face)",
    EntityKind.CREATURE: "upper third (head)",
    EntityKind.PORTRAIT: "eyes",
    EntityKind.WEAPON: "diagonal axis",
}


class CompositionResult(BaseModel):
    composition: Composition
    part_z_orders: dict[str, int] = Field(default_factory=dict)


def build_composition(context: PlanningContext) -> CompositionResult:
    """Deterministic composition plan — the mock backend's response and offline fast planner."""
    intent = context.output("intent", IntentResult)
    art = context.output("art-director", ArtDirectionResult)
    kind = intent.entity.kind

    if kind in _EDGE_TO_EDGE:
        composition = Composition(framing="edge-to-edge", margin_fraction=0.0)
    elif kind is EntityKind.WEAPON:
        composition = Composition(framing="diagonal", margin_fraction=0.1)
    else:
        margin = 0.15 if kind in _TIGHT_MARGIN else 0.1
        composition = Composition(
            framing=art.camera.framing, margin_fraction=margin, balance="symmetric"
        )
    composition.focal_point = _FOCAL_POINTS.get(kind, "center")

    # Draw order: keep the intent's back-to-front ordering, but glowing effects always render last.
    z_orders = {part.name: part.z_order for part in intent.entity.parts}
    if "glow" in z_orders and z_orders:
        z_orders["glow"] = max(z_orders.values()) + 1
    return CompositionResult(composition=composition, part_z_orders=z_orders)


class CompositionAgent(Agent):
    name = "composition"
    output_model = CompositionResult
    dependencies: tuple[str, ...] = ("intent", "art-director")

    def build_call(self, context: PlanningContext) -> AgentCall:
        return AgentCall(
            agent=self.name,
            deterministic=build_composition(context),
            system="You are a composition-planning agent for a pixel-art generator.",
            instructions=(
                "Given the parsed entity and camera, choose framing, margin, focal point, and the "
                "back-to-front draw order of the parts. Respond as structured JSON."
            ),
            context={"entity_kind": context.output("intent", IntentResult).entity.kind.value},
        )
