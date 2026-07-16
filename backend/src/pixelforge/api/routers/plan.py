"""Planning endpoint: preview the Scene Graph a request would produce (D-009/D-010).

Always available (independent of ``planning_enabled``, which only governs whether generation routes
through the planner). Returns the compiled positive prompt in ``provenance.expanded_prompt`` so a
client can show what the agents decided before spending a generation.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from pixelforge.agents.planning_backends.registry import get_planning_backend
from pixelforge.agents.runtime import PlanningRuntime
from pixelforge.api.state import AppState, get_state
from pixelforge.core.errors import UnknownRegistryKeyError
from pixelforge.core.models import GenerationRequest
from pixelforge.core.scene_graph import SceneGraph
from pixelforge.generation.plan_compiler import compile_prompt

router = APIRouter(prefix="/api", tags=["planning"])


@router.post("/plan", response_model=SceneGraph)
async def plan(request: GenerationRequest, state: AppState = Depends(get_state)) -> SceneGraph:
    try:
        style = state.styles.get(request.style)
        state.modes.get(request.mode)
        if request.palette_id:
            state.palettes.get(request.palette_id)
    except UnknownRegistryKeyError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    runtime = state.planner or PlanningRuntime(
        backend=get_planning_backend(state.settings.planning_backend),
        modes=state.modes,
        styles=state.styles,
    )
    graph = runtime.plan(request)
    graph.provenance.expanded_prompt = compile_prompt(graph, style)
    return graph
