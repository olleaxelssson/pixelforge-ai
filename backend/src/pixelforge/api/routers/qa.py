"""Pixel QA endpoint: analyze (and optionally repair) a sprite (D-013)."""

from __future__ import annotations

import base64
import io

from fastapi import APIRouter, Depends, HTTPException
from PIL import Image
from pydantic import BaseModel

from pixelforge.api.state import AppState, get_state
from pixelforge.core.errors import UnknownRegistryKeyError
from pixelforge.qa.models import DetectorContext, QAReport
from pixelforge.qa.repair_loop import RepairLoop, RepairLoopReport

router = APIRouter(prefix="/api/qa", tags=["qa"])


class QARequest(BaseModel):
    image_base64: str
    max_colors: int = 16
    transparent_background: bool = True
    palette_id: str | None = None
    lighting_direction: str | None = None
    subject: str | None = None  # intended subject, enables the semantic critic (D-013)
    repair: bool = False
    # Layer 2 (D-013): regenerate failing regions for up to ``max_iterations`` bounded passes.
    repair_loop: bool = False
    max_iterations: int = 2


class QAResponse(BaseModel):
    report: QAReport
    repaired_image_base64: str | None = None
    repair_loop: RepairLoopReport | None = None


def _decode(data: str) -> Image.Image:
    if "," in data:
        data = data.split(",", 1)[1]
    try:
        return Image.open(io.BytesIO(base64.b64decode(data))).convert("RGBA")
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=422, detail="invalid image data") from exc


@router.post("", response_model=QAResponse)
async def run_qa(request: QARequest, state: AppState = Depends(get_state)) -> QAResponse:
    image = _decode(request.image_base64)
    palette = None
    if request.palette_id:
        try:
            palette = state.palettes.get(request.palette_id).as_rgb()
        except UnknownRegistryKeyError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    context = DetectorContext(
        max_colors=request.max_colors,
        transparent_background=request.transparent_background,
        palette=palette,
        lighting_direction=request.lighting_direction,
        subject=request.subject,
    )

    if request.repair_loop:
        loop = RepairLoop(engine=state.qa, max_iterations=max(1, min(request.max_iterations, 5)))
        final, loop_report = loop.run(image, context)
        buffer = io.BytesIO()
        final.save(buffer, format="PNG")
        encoded = base64.b64encode(buffer.getvalue()).decode()
        return QAResponse(
            report=loop_report.final, repaired_image_base64=encoded, repair_loop=loop_report
        )

    if request.repair:
        repaired, report = state.qa.repair(image, context)
        buffer = io.BytesIO()
        repaired.save(buffer, format="PNG")
        encoded = base64.b64encode(buffer.getvalue()).decode()
        return QAResponse(report=report, repaired_image_base64=encoded)

    return QAResponse(report=state.qa.run(image, context))
