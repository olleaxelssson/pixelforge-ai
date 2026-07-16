"""Intent agent: parse the request into a structured entity + constraints (D-010).

Turns "red knight with a flaming sword" into a typed :class:`Entity` (kind, subject, parts,
materials) plus the size/palette/background constraints implied by the mode and request. The
deterministic heuristic here is what the ``MockPlanningBackend`` returns; a real LLM backend would
produce the same shape from ``system``/``instructions``.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from pixelforge.agents.base import Agent, PlanningContext
from pixelforge.agents.planning_backends.base import AgentCall
from pixelforge.core.models import GenerationRequest
from pixelforge.core.scene_graph import (
    Constraints,
    Entity,
    EntityKind,
    Material,
    MaterialKind,
    Part,
)

_MODE_TO_KIND: dict[str, EntityKind] = {
    "character": EntityKind.CHARACTER,
    "creature": EntityKind.CREATURE,
    "item": EntityKind.ITEM,
    "weapon": EntityKind.WEAPON,
    "armor": EntityKind.ARMOR,
    "environment": EntityKind.ENVIRONMENT,
    "tileset": EntityKind.TILE,
    "icon": EntityKind.ICON,
    "ui-element": EntityKind.UI,
    "portrait": EntityKind.PORTRAIT,
    "background": EntityKind.BACKGROUND,
    "sprite-sheet": EntityKind.CHARACTER,
}

# Ordered keyword → (part name, material) heuristics. First keyword hit per group wins.
_KEYWORD_PARTS: list[tuple[tuple[str, ...], str, MaterialKind]] = [
    (("sword", "blade", "dagger", "axe", "spear", "scythe"), "blade", MaterialKind.METAL),
    (("shield", "buckler"), "shield", MaterialKind.METAL),
    (("helmet", "helm"), "helmet", MaterialKind.METAL),
    (("armor", "plate", "mail", "breastplate"), "armor", MaterialKind.METAL),
    (("cape", "cloak"), "cape", MaterialKind.CLOTH),
    (("robe", "tunic", "cloth"), "garment", MaterialKind.CLOTH),
    (("boot", "glove", "belt"), "leatherwork", MaterialKind.LEATHER),
    (("potion", "flask", "vial", "bottle"), "flask", MaterialKind.GEM),
    (("gem", "crystal", "jewel", "diamond"), "gem", MaterialKind.GEM),
    (("staff", "wand", "bow"), "weapon-haft", MaterialKind.WOOD),
    (("wing", "feather"), "wing", MaterialKind.ORGANIC),
    (("fire", "flame", "flaming", "magic", "glow"), "glow", MaterialKind.ENERGY),
]

_CHARACTER_KINDS = {EntityKind.CHARACTER, EntityKind.CREATURE, EntityKind.PORTRAIT}


class IntentResult(BaseModel):
    entity: Entity
    constraints: Constraints
    tags: list[str] = Field(default_factory=list)
    expanded_subject: str = ""


def _detect_parts(prompt: str) -> tuple[list[Part], list[Material]]:
    lowered = prompt.lower()
    parts: list[Part] = []
    materials: dict[str, Material] = {}
    for z, (keywords, part_name, material_kind) in enumerate(_KEYWORD_PARTS):
        if any(keyword in lowered for keyword in keywords):
            material_name = material_kind.value
            materials.setdefault(material_name, Material(name=material_name, kind=material_kind))
            parts.append(Part(name=part_name, z_order=z, material=material_name))
    return parts, list(materials.values())


def _constraints(request: GenerationRequest) -> Constraints:
    return Constraints(
        width=request.width,
        height=request.height,
        transparent_background=request.transparent_background,
        max_colors=request.max_colors,
        dither=request.dither.value,
        outline=True,
    )


def build_intent_result(context: PlanningContext) -> IntentResult:
    """Deterministic intent parse — reused by the mock backend and as the offline fast planner."""
    request = context.request
    subject = request.prompt.strip()
    kind = _MODE_TO_KIND.get(context.mode.id, EntityKind.GENERIC)
    parts, materials = _detect_parts(subject)
    if kind in _CHARACTER_KINDS:
        parts.insert(0, Part(name="body", z_order=-1))
    entity = Entity(
        kind=kind, subject=subject, intent=context.mode.name, parts=parts, materials=materials
    )
    tags = [kind.value, *sorted({m.kind.value for m in materials})]
    return IntentResult(
        entity=entity,
        constraints=_constraints(request),
        tags=tags,
        expanded_subject=subject,
    )


class IntentAgent(Agent):
    name = "intent"
    output_model = IntentResult
    dependencies: tuple[str, ...] = ()

    def build_call(self, context: PlanningContext) -> AgentCall:
        result = build_intent_result(context)
        return AgentCall(
            agent=self.name,
            deterministic=result,
            system="You are an intent-parsing agent for a pixel-art generator.",
            instructions=(
                "Extract the entity kind, subject, its distinct parts and their materials, and the "
                "size/palette/background constraints. Respond as structured JSON."
            ),
            context={"prompt": context.request.prompt, "mode": context.mode.id},
        )
