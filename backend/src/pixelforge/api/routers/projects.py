"""Project persistence endpoints (autosave, session recovery)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from pixelforge.api.state import AppState, get_state
from pixelforge.projects.store import Project

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("", response_model=list[Project])
async def list_projects(state: AppState = Depends(get_state)) -> list[Project]:
    return state.projects.list()


@router.get("/latest", response_model=Project | None)
async def recover_latest(state: AppState = Depends(get_state)) -> Project | None:
    return state.projects.recover_latest()


@router.get("/{project_id}", response_model=Project)
async def get_project(project_id: str, state: AppState = Depends(get_state)) -> Project:
    project = state.projects.get(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")
    return project


@router.post("", response_model=Project)
async def save_project(project: Project, state: AppState = Depends(get_state)) -> Project:
    return state.projects.save(project)


@router.delete("/{project_id}")
async def delete_project(project_id: str, state: AppState = Depends(get_state)) -> dict[str, bool]:
    if not state.projects.delete(project_id):
        raise HTTPException(status_code=404, detail="project not found")
    return {"deleted": True}
