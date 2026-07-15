"""Project persistence: JSON project files with autosave support.

A project bundles generated assets, editor documents, and palettes. The
frontend autosaves editor state here; ``recover_latest`` supports session
recovery after a crash.
"""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

from pydantic import BaseModel, Field


class EditorLayer(BaseModel):
    name: str = "Layer 1"
    visible: bool = True
    # RGBA pixel data, base64-encoded, row-major; None for empty layers.
    pixels_base64: str | None = None


class EditorDocument(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    name: str = "Untitled"
    width: int = 32
    height: int = 32
    layers: list[EditorLayer] = Field(default_factory=lambda: [EditorLayer()])
    frames: int = 1


class Project(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    name: str = "Untitled Project"
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    documents: list[EditorDocument] = Field(default_factory=list)
    generated_filenames: list[str] = Field(default_factory=list)
    palette_ids: list[str] = Field(default_factory=list)


class ProjectStore:
    def __init__(self, projects_dir: Path) -> None:
        self._dir = projects_dir

    def _path(self, project_id: str) -> Path:
        return self._dir / f"{project_id}.json"

    def list(self) -> list[Project]:
        projects = []
        for path in sorted(self._dir.glob("*.json")):
            try:
                projects.append(Project(**json.loads(path.read_text())))
            except (json.JSONDecodeError, ValueError):
                continue  # skip corrupt files; never block startup
        return sorted(projects, key=lambda p: p.updated_at, reverse=True)

    def get(self, project_id: str) -> Project | None:
        path = self._path(project_id)
        if not path.exists():
            return None
        return Project(**json.loads(path.read_text()))

    def save(self, project: Project) -> Project:
        project.updated_at = time.time()
        self._path(project.id).write_text(project.model_dump_json(indent=2))
        return project

    def delete(self, project_id: str) -> bool:
        path = self._path(project_id)
        if path.exists():
            path.unlink()
            return True
        return False

    def recover_latest(self) -> Project | None:
        projects = self.list()
        return projects[0] if projects else None
