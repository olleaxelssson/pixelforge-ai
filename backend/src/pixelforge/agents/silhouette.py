"""Silhouette planner: a coarse shape intent for the sprite (D-010, M11).

Emits a low-resolution occupancy grid describing where the subject should sit. The plan compiler
renders it into a Stage-A control map (silhouette conditioning); QA's silhouette detector judges the
result against the same intent. Depends on the Intent agent (kind) and the Composition planner
(margin/framing).
"""

from __future__ import annotations

from pydantic import BaseModel

from pixelforge.agents.base import Agent, PlanningContext
from pixelforge.agents.composition import CompositionResult
from pixelforge.agents.intent import IntentResult
from pixelforge.agents.planning_backends.base import AgentCall
from pixelforge.core.scene_graph import EntityKind, SilhouettePlan

GRID_SIZE = 16

_HUMANOID = {EntityKind.CHARACTER, EntityKind.CREATURE}
_BLOB = {EntityKind.ITEM, EntityKind.ICON, EntityKind.ARMOR, EntityKind.GENERIC}
_FULL = {EntityKind.TILE, EntityKind.BACKGROUND, EntityKind.ENVIRONMENT, EntityKind.UI}


class SilhouetteResult(BaseModel):
    silhouette: SilhouettePlan


def _cells(margin_fraction: float) -> tuple[int, int]:
    margin = round(GRID_SIZE * margin_fraction)
    return margin, GRID_SIZE - margin


def _humanoid_grid(lo: int, hi: int) -> list[list[bool]]:
    grid = [[False] * GRID_SIZE for _ in range(GRID_SIZE)]
    span = hi - lo
    center = GRID_SIZE // 2
    head_end = lo + max(1, span // 4)
    torso_end = lo + (span * 5) // 8
    for y in range(lo, hi):
        if y < head_end:
            half = max(1, span // 6)  # head: narrow
        elif y < torso_end:
            half = max(2, span // 4)  # torso + arms: widest
        else:
            half = max(1, span // 5)  # legs
        for x in range(center - half, center + half):
            if 0 <= x < GRID_SIZE:
                grid[y][x] = True
    return grid


def _blob_grid(lo: int, hi: int) -> list[list[bool]]:
    grid = [[False] * GRID_SIZE for _ in range(GRID_SIZE)]
    center = (GRID_SIZE - 1) / 2.0
    radius = (hi - lo) / 2.0
    for y in range(GRID_SIZE):
        for x in range(GRID_SIZE):
            if (x - center) ** 2 + (y - center) ** 2 <= radius**2:
                grid[y][x] = True
    return grid


def _diagonal_grid(lo: int, hi: int) -> list[list[bool]]:
    grid = [[False] * GRID_SIZE for _ in range(GRID_SIZE)]
    for y in range(lo, hi):
        x_center = GRID_SIZE - 1 - y  # bottom-left → top-right axis
        for x in range(x_center - 1, x_center + 2):
            if lo <= x < hi:
                grid[y][x] = True
    return grid


def build_silhouette(context: PlanningContext) -> SilhouetteResult:
    """Deterministic silhouette plan — the mock backend's response and offline fast planner."""
    intent = context.output("intent", IntentResult)
    composition = context.output("composition", CompositionResult)
    kind = intent.entity.kind
    lo, hi = _cells(composition.composition.margin_fraction)

    if kind in _FULL:
        grid = [[True] * GRID_SIZE for _ in range(GRID_SIZE)]
        notes = "edge-to-edge fill"
    elif kind in _HUMANOID:
        grid = _humanoid_grid(lo, hi)
        notes = "head/torso/legs capsule, readable outline"
    elif kind is EntityKind.WEAPON:
        grid = _diagonal_grid(lo, hi)
        notes = "diagonal weapon axis"
    elif kind is EntityKind.PORTRAIT:
        grid = _blob_grid(lo, hi)
        notes = "head-and-shoulders mass"
    else:
        grid = _blob_grid(lo, hi)
        notes = "centered compact mass"

    rows = ["".join("1" if cell else "0" for cell in row) for row in grid]
    return SilhouetteResult(silhouette=SilhouettePlan(grid=rows, notes=notes))


class SilhouetteAgent(Agent):
    name = "silhouette"
    output_model = SilhouetteResult
    dependencies: tuple[str, ...] = ("intent", "composition")

    def build_call(self, context: PlanningContext) -> AgentCall:
        return AgentCall(
            agent=self.name,
            deterministic=build_silhouette(context),
            system="You are a silhouette-planning agent for a pixel-art generator.",
            instructions=(
                "Given the entity kind and composition, produce a coarse occupancy grid (rows of "
                "'0'/'1') describing a readable silhouette. Respond as structured JSON."
            ),
            context={"entity_kind": context.output("intent", IntentResult).entity.kind.value},
        )
