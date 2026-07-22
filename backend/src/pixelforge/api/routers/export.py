"""Export endpoints: convert generated/edited frames into deliverable files."""

from __future__ import annotations

import base64
import io
import tempfile
import zipfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from PIL import Image
from pydantic import BaseModel, Field

from pixelforge.api.state import AppState, get_state
from pixelforge.core.errors import UnknownRegistryKeyError
from pixelforge.exporters.base import ExportAsset, ExportOptions
from pixelforge.exporters.registry import get_exporter, list_exporters

router = APIRouter(prefix="/api/export", tags=["export"])


class ExportRequest(BaseModel):
    format_id: str
    # Frames as generated-image filenames and/or base64 PNGs (editor content).
    filenames: list[str] = Field(default_factory=list)
    frames_base64: list[str] = Field(default_factory=list)
    options: ExportOptions = Field(default_factory=ExportOptions)


@router.get("/formats")
async def formats() -> list[dict[str, str]]:
    return list_exporters()


@router.post("")
async def export(request: ExportRequest, state: AppState = Depends(get_state)) -> Response:
    frames: list[Image.Image] = []
    for filename in request.filenames:
        if "/" in filename or ".." in filename:
            raise HTTPException(status_code=400, detail="invalid filename")
        path = state.settings.outputs_dir / filename
        if not path.exists():
            raise HTTPException(status_code=404, detail=f"image not found: {filename}")
        frames.append(Image.open(path).convert("RGBA"))
    for data in request.frames_base64:
        if "," in data:
            data = data.split(",", 1)[1]
        frames.append(Image.open(io.BytesIO(base64.b64decode(data))).convert("RGBA"))
    if not frames:
        raise HTTPException(status_code=422, detail="no frames provided")

    try:
        exporter = get_exporter(request.format_id)
    except UnknownRegistryKeyError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    with tempfile.TemporaryDirectory() as tmp:
        paths = exporter.export(ExportAsset(frames=frames), request.options, Path(tmp))
        if len(paths) == 1:
            payload = paths[0].read_bytes()
            media = {".gif": "image/gif", ".png": "image/png"}.get(
                paths[0].suffix, "application/octet-stream"
            )
            headers = {"Content-Disposition": f'attachment; filename="{paths[0].name}"'}
            return Response(content=payload, media_type=media, headers=headers)
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            for path in paths:
                archive.write(path, arcname=path.name)
        headers = {"Content-Disposition": f'attachment; filename="{request.options.base_name}.zip"'}
        return Response(content=buffer.getvalue(), media_type="application/zip", headers=headers)
