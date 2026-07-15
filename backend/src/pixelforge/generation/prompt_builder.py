"""Compose the final diffusion prompt from mode, style, and user input."""

from __future__ import annotations

from pixelforge.core.models import GenerationRequest
from pixelforge.modes.registry import GenerationMode
from pixelforge.styles.registry import StylePreset


def build_prompt(request: GenerationRequest, mode: GenerationMode, style: StylePreset) -> str:
    subject = mode.prompt_template.format(prompt=request.prompt.strip())
    parts = [style.prompt_prefix, subject, style.prompt_suffix]
    if request.transparent_background:
        parts.append("isolated on plain solid background")
    if request.lighting_direction and request.lighting_direction != "none":
        parts.append(f"light source from {request.lighting_direction}")
    if request.shading_style and request.shading_style != "standard":
        parts.append(f"{request.shading_style} shading")
    return ", ".join(p.strip().strip(",") for p in parts if p.strip())


def build_negative_prompt(request: GenerationRequest, style: StylePreset) -> str:
    parts = [style.negative_prompt, request.negative_prompt]
    return ", ".join(p.strip() for p in parts if p.strip())
