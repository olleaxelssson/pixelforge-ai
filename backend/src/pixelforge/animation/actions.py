"""Animation action definitions used to prompt per-frame generation."""

from __future__ import annotations

from pydantic import BaseModel


class AnimationAction(BaseModel):
    id: str
    name: str
    frame_count: int
    frame_descriptions: list[str]
    loop: bool = True


ANIMATION_ACTIONS: list[AnimationAction] = [
    AnimationAction(
        id="idle",
        name="Idle",
        frame_count=4,
        frame_descriptions=[
            "standing relaxed, arms at rest",
            "standing relaxed, slight inhale, chest raised subtly",
            "standing relaxed, peak of breath",
            "standing relaxed, slight exhale",
        ],
    ),
    AnimationAction(
        id="walk",
        name="Walk",
        frame_count=6,
        frame_descriptions=[
            "walking, right foot forward contact",
            "walking, right leg passing under body",
            "walking, left foot lifting, body highest",
            "walking, left foot forward contact",
            "walking, left leg passing under body",
            "walking, right foot lifting, body highest",
        ],
    ),
    AnimationAction(
        id="run",
        name="Run",
        frame_count=6,
        frame_descriptions=[
            "running, full stride, both legs extended",
            "running, right foot landing, body leaning forward",
            "running, gathered pose, knees bent",
            "running, pushing off, left leg extending back",
            "running, airborne, arms pumping",
            "running, left foot landing",
        ],
    ),
    AnimationAction(
        id="attack",
        name="Attack",
        frame_count=5,
        loop=False,
        frame_descriptions=[
            "attack windup, weapon raised back",
            "attack anticipation, weight shifting forward",
            "attack swing, weapon mid-arc, motion emphasis",
            "attack impact, weapon fully extended",
            "attack recovery, returning to guard stance",
        ],
    ),
    AnimationAction(
        id="death",
        name="Death",
        frame_count=5,
        loop=False,
        frame_descriptions=[
            "taking fatal hit, recoiling",
            "stumbling backward, losing balance",
            "falling, knees buckling",
            "collapsed on ground, partially down",
            "lying still on the ground",
        ],
    ),
    AnimationAction(
        id="hurt",
        name="Hurt",
        frame_count=3,
        loop=False,
        frame_descriptions=[
            "flinching from hit, head snapped back",
            "recoiling, body bent",
            "recovering to stance",
        ],
    ),
    AnimationAction(
        id="jump",
        name="Jump",
        frame_count=5,
        loop=False,
        frame_descriptions=[
            "crouching, coiled to jump",
            "launching upward, legs extending",
            "airborne at apex, legs tucked",
            "descending, legs reaching down",
            "landing, knees absorbing impact",
        ],
    ),
    AnimationAction(
        id="cast",
        name="Cast",
        frame_count=5,
        loop=False,
        frame_descriptions=[
            "spell windup, hands gathering energy",
            "channeling, glowing focus between hands",
            "casting thrust, arms extended forward",
            "spell release, burst of energy",
            "follow-through, arms lowering",
        ],
    ),
    AnimationAction(
        id="mining",
        name="Mining",
        frame_count=4,
        frame_descriptions=[
            "raising pickaxe overhead",
            "pickaxe at peak height",
            "swinging pickaxe down",
            "pickaxe striking rock, impact debris",
        ],
    ),
    AnimationAction(
        id="fishing",
        name="Fishing",
        frame_count=4,
        frame_descriptions=[
            "casting fishing rod back",
            "flicking rod forward, line flying",
            "waiting, line in water",
            "rod bending, reeling in",
        ],
    ),
    AnimationAction(
        id="woodcutting",
        name="Woodcutting",
        frame_count=4,
        frame_descriptions=[
            "raising axe to shoulder",
            "axe at peak of swing",
            "swinging axe into tree",
            "axe embedded in trunk, chips flying",
        ],
    ),
    AnimationAction(
        id="crafting",
        name="Crafting",
        frame_count=4,
        frame_descriptions=[
            "leaning over workbench, tool raised",
            "striking work piece",
            "inspecting the piece up close",
            "adjusting with tool, sparks or dust",
        ],
    ),
    AnimationAction(
        id="farming",
        name="Farming",
        frame_count=4,
        frame_descriptions=[
            "raising hoe above soil",
            "hoe at top of swing",
            "driving hoe into soil",
            "dragging hoe through earth",
        ],
    ),
]


def get_action(action_id: str) -> AnimationAction | None:
    return next((a for a in ANIMATION_ACTIONS if a.id == action_id), None)
