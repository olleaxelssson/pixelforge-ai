"""Dataset endpoint (M4, D-001): analyze uploaded sprites → validation, dedup, captions, manifest.

Works entirely in memory — the frontend uploads base64 images, we validate/dedup/caption them and
return a :class:`DatasetReport` (with an inline manifest + LoRA config), never touching disk.
Writing ``manifest.jsonl`` / ``lora_config.json`` is the CLI's job (it has a real folder to scan).
"""

from __future__ import annotations

import base64
import binascii
import io

from fastapi import APIRouter, HTTPException
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel

from pixelforge.dataset.builder import LoadedImage, build_dataset
from pixelforge.dataset.models import DatasetReport
from pixelforge.dataset.phash import DEFAULT_DUP_DISTANCE

router = APIRouter(prefix="/api/dataset", tags=["dataset"])


class DatasetUpload(BaseModel):
    name: str
    image_base64: str


class DatasetRequest(BaseModel):
    images: list[DatasetUpload]
    dup_distance: int = DEFAULT_DUP_DISTANCE


def _load(upload: DatasetUpload) -> LoadedImage:
    data = upload.image_base64
    if "," in data:
        data = data.split(",", 1)[1]
    try:
        raw = base64.b64decode(data)
        image = Image.open(io.BytesIO(raw))
        image.load()
        return LoadedImage(name=upload.name, image=image.convert("RGBA"))
    except (UnidentifiedImageError, OSError, ValueError, binascii.Error) as exc:
        return LoadedImage(name=upload.name, load_error=f"unreadable: {exc}")


@router.post("", response_model=DatasetReport)
async def analyze_dataset(request: DatasetRequest) -> DatasetReport:
    if not request.images:
        raise HTTPException(status_code=422, detail="no images provided")
    inputs = [_load(upload) for upload in request.images]
    return build_dataset(
        inputs, root="uploaded", dup_distance=max(0, min(request.dup_distance, 32))
    )
