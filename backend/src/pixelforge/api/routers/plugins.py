"""Plugin report endpoint (D-014): what was discovered, loaded, and skipped at startup."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from pixelforge.api.state import AppState, get_state
from pixelforge.plugins.manifest import PluginReport

router = APIRouter(prefix="/api", tags=["plugins"])


@router.get("/plugins", response_model=PluginReport)
async def plugin_report(state: AppState = Depends(get_state)) -> PluginReport:
    return state.plugins
