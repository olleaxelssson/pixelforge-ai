"""Animation planner: pick the action a character sprite should be posed in (D-010, M11).

Maps prompt keywords onto the registered animation actions (walk, attack, cast, ...), defaulting to
idle for characters/creatures and to no animation state for static asset kinds. Depends on the
Intent agent. Cross-frame sequence generation remains the animation milestone (M3); this planner
sets the single-frame pose intent that the compiler turns into a prompt phrase.
"""

from __future__ import annotations

from pydantic import BaseModel

from pixelforge.agents.base import Agent, PlanningContext
from pixelforge.agents.intent import IntentResult
from pixelforge.agents.planning_backends.base import AgentCall
from pixelforge.animation.actions import get_action
from pixelforge.core.scene_graph import AnimationState, EntityKind

_ANIMATED_KINDS = {EntityKind.CHARACTER, EntityKind.CREATURE}

# Ordered keyword → action id; the first hit wins (specific actions before generic movement).
_KEYWORDS: list[tuple[tuple[str, ...], str]] = [
    (("attacking", "attack", "striking", "slashing", "swinging"), "attack"),
    (("casting", "cast", "spellcasting", "conjuring"), "cast"),
    (("running", " run ", "sprinting"), "run"),
    (("walking", " walk ", "strolling"), "walk"),
    (("jumping", " jump ", "leaping"), "jump"),
    (("dying", "death", "defeated"), "death"),
    (("hurt", "wounded", "flinching"), "hurt"),
    (("mining",), "mining"),
    (("fishing",), "fishing"),
    (("woodcutting", "chopping wood"), "woodcutting"),
    (("crafting", "smithing", "forging"), "crafting"),
    (("farming", "hoeing", "tilling"), "farming"),
]

_DIRECTIONS: list[tuple[str, str]] = [
    ("facing left", "west"),
    ("facing right", "east"),
    ("facing away", "north"),
    ("from behind", "north"),
]


class AnimationPlanResult(BaseModel):
    animation: AnimationState | None = None


def build_animation_plan(context: PlanningContext) -> AnimationPlanResult:
    """Deterministic animation intent — the mock backend's response and offline fast planner."""
    intent = context.output("intent", IntentResult)
    if intent.entity.kind not in _ANIMATED_KINDS:
        return AnimationPlanResult(animation=None)

    lowered = f" {context.request.prompt.lower()} "
    action_id = "idle"
    for keywords, candidate in _KEYWORDS:
        if any(keyword in lowered for keyword in keywords) and get_action(candidate) is not None:
            action_id = candidate
            break

    direction = "south"
    for phrase, compass in _DIRECTIONS:
        if phrase in lowered:
            direction = compass
            break
    return AnimationPlanResult(animation=AnimationState(action=action_id, direction=direction))


class AnimationAgent(Agent):
    name = "animation"
    output_model = AnimationPlanResult
    dependencies: tuple[str, ...] = ("intent",)

    def build_call(self, context: PlanningContext) -> AgentCall:
        return AgentCall(
            agent=self.name,
            deterministic=build_animation_plan(context),
            system="You are an animation-planning agent for a pixel-art generator.",
            instructions=(
                "Choose the animation action and facing direction implied by the prompt (idle "
                "if unspecified); static kinds get no animation state. Respond as structured JSON."
            ),
            context={"prompt": context.request.prompt},
        )
