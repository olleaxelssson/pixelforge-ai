"""Animation endpoints (M3/M18): list actions, generate a frame sequence."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from starlette.concurrency import run_in_threadpool

from pixelforge.animation.actions import ANIMATION_ACTIONS, AnimationAction
from pixelforge.animation.sequence import AnimationRequest, AnimationResult
from pixelforge.api.state import AppState, get_state
from pixelforge.core.errors import UnknownRegistryKeyError

router = APIRouter(prefix="/api/animation", tags=["animation"])


@router.get("/actions", response_model=list[AnimationAction])
async def list_actions() -> list[AnimationAction]:
    return ANIMATION_ACTIONS


@router.post("/generate", response_model=AnimationResult)
async def generate(
    request: AnimationRequest, state: AppState = Depends(get_state)
) -> AnimationResult:
    try:
        state.modes.get(request.mode)
        state.styles.get(request.style)
        if request.palette_id:
            state.palettes.get(request.palette_id)
    except UnknownRegistryKeyError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    try:
        # Runs the per-frame pipeline off the event loop; the mock is fast, real backends are slow.
        return await run_in_threadpool(
            state.animation.generate, "anim", request, lambda _stage, _percent: None
        )
    except UnknownRegistryKeyError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
