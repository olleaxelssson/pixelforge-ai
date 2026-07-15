"""StylePreset model."""

from __future__ import annotations

from pydantic import BaseModel, Field


class StylePreset(BaseModel):
    id: str
    name: str
    description: str = ""
    prompt_prefix: str = ""
    prompt_suffix: str = ""
    negative_prompt: str = ""
    default_palette_id: str | None = None
    default_max_colors: int | None = None
    outline: bool = True
    tags: list[str] = Field(default_factory=list)
