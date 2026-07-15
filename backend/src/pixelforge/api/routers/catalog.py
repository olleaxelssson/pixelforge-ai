"""Read-only catalogs: modes, styles, animation actions, backends, system info."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from pixelforge import __version__
from pixelforge.animation.actions import ANIMATION_ACTIONS, AnimationAction
from pixelforge.api.state import AppState, get_state
from pixelforge.generation.backends.registry import list_backends
from pixelforge.models_manager.device import device_info
from pixelforge.modes.registry import GenerationMode
from pixelforge.styles.registry import StylePreset

router = APIRouter(prefix="/api", tags=["catalog"])

SUPPORTED_SIZES = [16, 24, 32, 48, 64, 96, 128, 256]


@router.get("/modes", response_model=list[GenerationMode])
async def list_modes(state: AppState = Depends(get_state)) -> list[GenerationMode]:
    return state.modes.list()


@router.get("/styles", response_model=list[StylePreset])
async def list_styles(state: AppState = Depends(get_state)) -> list[StylePreset]:
    return state.styles.list()


@router.get("/animations", response_model=list[AnimationAction])
async def list_animations() -> list[AnimationAction]:
    return ANIMATION_ACTIONS


@router.get("/system")
async def system_info() -> dict[str, object]:
    return {
        "version": __version__,
        "backends": list_backends(),
        "device": device_info(),
        "supported_sizes": SUPPORTED_SIZES,
    }
