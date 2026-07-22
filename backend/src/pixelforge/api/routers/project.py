"""Project bundle endpoints (M25): save/load the portable ``.pforge`` workspace archive."""

from __future__ import annotations

import base64
import binascii

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from pixelforge.projects.bundle import (
    ProjectBundle,
    ProjectBundleError,
    bundle_bytes,
    read_bundle,
)

router = APIRouter(prefix="/api/project", tags=["project"])


class SpriteUpload(BaseModel):
    name: str
    image_base64: str


class SaveRequest(BaseModel):
    name: str = "Untitled Project"
    created_at: float = 0.0
    sprites: list[SpriteUpload] = Field(default_factory=list)
    palettes: list[dict[str, object]] = Field(default_factory=list)
    characters: list[dict[str, object]] = Field(default_factory=list)
    project: dict[str, object] = Field(default_factory=dict)
    metadata: dict[str, object] = Field(default_factory=dict)


class LoadRequest(BaseModel):
    bundle_base64: str


class LoadResponse(BaseModel):
    manifest: ProjectBundle
    sprites: list[SpriteUpload]


def _decode(data: str) -> bytes:
    if "," in data:
        data = data.split(",", 1)[1]
    try:
        return base64.b64decode(data)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=422, detail="invalid base64 data") from exc


@router.post("/save")
async def save(request: SaveRequest) -> Response:
    images = {s.name: _decode(s.image_base64) for s in request.sprites}
    bundle = ProjectBundle(
        name=request.name,
        created_at=request.created_at,
        sprites=[s.name for s in request.sprites],
        palettes=request.palettes,
        characters=request.characters,
        project=request.project,
        metadata=request.metadata,
    )
    try:
        payload = bundle_bytes(bundle, images)
    except ProjectBundleError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    safe = request.name.strip().replace("/", "_") or "project"
    headers = {"Content-Disposition": f'attachment; filename="{safe}.pforge"'}
    return Response(content=payload, media_type="application/octet-stream", headers=headers)


@router.post("/load", response_model=LoadResponse)
async def load(request: LoadRequest) -> LoadResponse:
    try:
        loaded = read_bundle(_decode(request.bundle_base64))
    except ProjectBundleError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return LoadResponse(
        manifest=loaded.bundle,
        sprites=[
            SpriteUpload(name=name, image_base64=base64.b64encode(data).decode())
            for name, data in sorted(loaded.images.items())
        ],
    )
