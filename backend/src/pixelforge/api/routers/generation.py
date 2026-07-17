"""Generation and job endpoints, including the WebSocket progress stream."""

from __future__ import annotations

import asyncio
import contextlib

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse

from pixelforge.api.state import AppState, get_state
from pixelforge.core.errors import UnknownRegistryKeyError
from pixelforge.core.models import GenerationRequest, Job, JobStatus

router = APIRouter(prefix="/api", tags=["generation"])


@router.post("/generate", response_model=Job, status_code=202)
async def submit_generation(
    request: GenerationRequest, state: AppState = Depends(get_state)
) -> Job:
    try:
        if request.character_id:
            # Apply the stored identity (prompt, palette lock, reference frame) before queueing.
            request = state.characters.apply_to_request(request.character_id, request)
        state.modes.get(request.mode)
        state.styles.get(request.style)
        if request.palette_id:
            state.palettes.get(request.palette_id)
    except UnknownRegistryKeyError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return await state.queue.submit(request)


@router.get("/jobs", response_model=list[Job])
async def list_jobs(state: AppState = Depends(get_state)) -> list[Job]:
    return state.queue.list_jobs()


@router.get("/jobs/{job_id}", response_model=Job)
async def get_job(job_id: str, state: AppState = Depends(get_state)) -> Job:
    job = state.queue.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return job


@router.post("/jobs/{job_id}/cancel")
async def cancel_job(job_id: str, state: AppState = Depends(get_state)) -> dict[str, bool]:
    return {"cancelled": state.queue.cancel(job_id)}


@router.get("/images/{filename}")
async def get_image(filename: str, state: AppState = Depends(get_state)) -> FileResponse:
    if "/" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="invalid filename")
    path = state.settings.outputs_dir / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="image not found")
    return FileResponse(path, media_type="image/png")


@router.websocket("/ws/jobs/{job_id}")
async def job_progress_stream(websocket: WebSocket, job_id: str) -> None:
    state: AppState = websocket.app.state.services
    job = state.queue.get(job_id)
    if job is None:
        await websocket.close(code=4404)
        return
    await websocket.accept()
    updates = state.queue.subscribe(job_id)
    try:
        await websocket.send_text(job.model_dump_json())
        while job.status in (JobStatus.QUEUED, JobStatus.RUNNING):
            with contextlib.suppress(asyncio.TimeoutError):
                job = await asyncio.wait_for(updates.get(), timeout=30.0)
                await websocket.send_text(job.model_dump_json())
    except WebSocketDisconnect:
        pass
    finally:
        state.queue.unsubscribe(job_id, updates)
