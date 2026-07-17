"""Character-memory endpoints (D-011): CRUD, reference frames, drift checks."""

from __future__ import annotations

import base64
import io

from fastapi import APIRouter, Depends, HTTPException
from PIL import Image
from pydantic import BaseModel

from pixelforge.api.state import AppState, get_state
from pixelforge.core.errors import UnknownRegistryKeyError
from pixelforge.memory.models import Character, CharacterIdentity, DriftResult

router = APIRouter(prefix="/api/characters", tags=["characters"])


class CreateCharacterRequest(BaseModel):
    name: str
    identity: CharacterIdentity
    palette_id: str | None = None


class FrameRequest(BaseModel):
    image_base64: str
    label: str = "variant"  # "passport" anchors the identity embedding


class DriftRequest(BaseModel):
    image_base64: str


def _decode(data: str) -> Image.Image:
    if "," in data:
        data = data.split(",", 1)[1]
    try:
        return Image.open(io.BytesIO(base64.b64decode(data))).convert("RGBA")
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=422, detail="invalid image data") from exc


@router.get("", response_model=list[Character])
async def list_characters(state: AppState = Depends(get_state)) -> list[Character]:
    return state.characters.list()


@router.post("", response_model=Character)
async def create_character(
    request: CreateCharacterRequest, state: AppState = Depends(get_state)
) -> Character:
    if request.palette_id:
        try:
            state.palettes.get(request.palette_id)
        except UnknownRegistryKeyError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    return state.characters.create(request.name, request.identity, request.palette_id)


@router.get("/{character_id}", response_model=Character)
async def get_character(character_id: str, state: AppState = Depends(get_state)) -> Character:
    try:
        return state.characters.get(character_id)
    except UnknownRegistryKeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/{character_id}")
async def delete_character(
    character_id: str, state: AppState = Depends(get_state)
) -> dict[str, bool]:
    if not state.characters.delete(character_id):
        raise HTTPException(status_code=404, detail="character not found")
    return {"deleted": True}


@router.post("/{character_id}/frames", response_model=Character)
async def add_frame(
    character_id: str, request: FrameRequest, state: AppState = Depends(get_state)
) -> Character:
    image = _decode(request.image_base64)
    try:
        return state.characters.add_reference_frame(character_id, image, request.label)
    except UnknownRegistryKeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{character_id}/drift", response_model=DriftResult)
async def check_drift(
    character_id: str, request: DriftRequest, state: AppState = Depends(get_state)
) -> DriftResult:
    image = _decode(request.image_base64)
    try:
        return state.characters.check_drift(character_id, image)
    except UnknownRegistryKeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
