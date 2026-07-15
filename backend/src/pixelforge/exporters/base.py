"""Exporter interface and shared export models."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from PIL import Image
from pydantic import BaseModel, Field


class ExportOptions(BaseModel):
    scale: int = Field(default=1, ge=1, le=16)  # integer nearest-neighbor upscale
    columns: int | None = None  # sprite-sheet layout
    padding: int = 0
    frame_duration_ms: int = 120
    base_name: str = "sprite"


class ExportAsset(BaseModel):
    model_config = {"arbitrary_types_allowed": True}

    frames: list[Image.Image]

    def scaled_frames(self, scale: int) -> list[Image.Image]:
        if scale <= 1:
            return self.frames
        return [
            f.resize((f.width * scale, f.height * scale), Image.Resampling.NEAREST)
            for f in self.frames
        ]


class Exporter(ABC):
    format_id: str = "abstract"
    display_name: str = "Abstract"

    @abstractmethod
    def export(self, asset: ExportAsset, options: ExportOptions, dest: Path) -> list[Path]:
        """Write files into ``dest`` and return the paths created."""
