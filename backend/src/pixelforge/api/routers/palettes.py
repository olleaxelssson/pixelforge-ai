"""Palette CRUD and extraction endpoints."""

from __future__ import annotations

import base64
import io

from fastapi import APIRouter, Depends, HTTPException
from PIL import Image
from pydantic import BaseModel

from pixelforge.api.state import AppState, get_state
from pixelforge.core.errors import UnknownRegistryKeyError
from pixelforge.palettes.model import Palette
from pixelforge.palettes.quantize import palette_from_image

router = APIRouter(prefix="/api/palettes", tags=["palettes"])


class ExtractRequest(BaseModel):
    image_base64: str
    max_colors: int = 16
    palette_id: str = "extracted"


@router.get("", response_model=list[Palette])
async def list_palettes(state: AppState = Depends(get_state)) -> list[Palette]:
    return state.palettes.list()


@router.get("/{palette_id}", response_model=Palette)
async def get_palette(palette_id: str, state: AppState = Depends(get_state)) -> Palette:
    try:
        return state.palettes.get(palette_id)
    except UnknownRegistryKeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("", response_model=Palette)
async def save_palette(palette: Palette, state: AppState = Depends(get_state)) -> Palette:
    if palette.builtin:
        raise HTTPException(status_code=422, detail="cannot overwrite builtin palettes")
    return state.palettes.save(palette)


@router.delete("/{palette_id}")
async def delete_palette(palette_id: str, state: AppState = Depends(get_state)) -> dict[str, bool]:
    try:
        state.palettes.delete(palette_id)
    except UnknownRegistryKeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"deleted": True}


@router.post("/extract", response_model=Palette)
async def extract(request: ExtractRequest) -> Palette:
    data = request.image_base64
    if "," in data:
        data = data.split(",", 1)[1]
    try:
        image = Image.open(io.BytesIO(base64.b64decode(data)))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=422, detail="invalid image data") from exc
    return palette_from_image(image, request.max_colors, request.palette_id)
