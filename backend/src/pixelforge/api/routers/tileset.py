"""Tileset endpoint (M23): generate a coherent, seam-locked terrain family."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from starlette.concurrency import run_in_threadpool

from pixelforge.api.state import AppState, get_state
from pixelforge.core.errors import UnknownRegistryKeyError
from pixelforge.tileset.service import TileSetRequest, TileSetResult

router = APIRouter(prefix="/api/tileset", tags=["tileset"])


@router.post("/generate", response_model=TileSetResult)
async def generate(request: TileSetRequest, state: AppState = Depends(get_state)) -> TileSetResult:
    try:
        state.modes.get(request.mode)
        state.styles.get(request.style)
        if request.palette_id:
            state.palettes.get(request.palette_id)
    except UnknownRegistryKeyError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    job_id = f"tileset_{uuid.uuid4().hex[:8]}"
    # Runs the per-variant pipeline off the event loop; the mock is fast, real backends are slow.
    return await run_in_threadpool(
        state.tileset.generate, job_id, request, lambda _stage, _percent: None
    )
