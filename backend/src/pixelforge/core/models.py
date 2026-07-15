"""Domain models shared across the backend."""

from __future__ import annotations

import uuid
from enum import Enum

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DitherMode(str, Enum):
    NONE = "none"
    ORDERED = "ordered"


class GenerationRequest(BaseModel):
    prompt: str
    negative_prompt: str = ""
    mode: str = "text-to-pixel"
    style: str = "modern-indie"
    width: int = Field(default=32, ge=8, le=512)
    height: int = Field(default=32, ge=8, le=512)
    seed: int | None = None
    batch_size: int = Field(default=1, ge=1, le=16)
    palette_id: str | None = None
    max_colors: int = Field(default=16, ge=2, le=256)
    dither: DitherMode = DitherMode.NONE
    transparent_background: bool = True
    outline_strength: float = Field(default=0.5, ge=0.0, le=1.0)
    lighting_direction: str = "top-left"
    shading_style: str = "standard"
    reference_image_base64: str | None = None
    reference_strength: float = Field(default=0.6, ge=0.0, le=1.0)


class GeneratedImage(BaseModel):
    filename: str
    width: int
    height: int
    seed: int
    palette_hex: list[str]


class GenerationResult(BaseModel):
    images: list[GeneratedImage] = Field(default_factory=list)


class JobProgress(BaseModel):
    stage: str = "queued"
    percent: float = 0.0


class Job(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    status: JobStatus = JobStatus.QUEUED
    request: GenerationRequest
    progress: JobProgress = Field(default_factory=JobProgress)
    result: GenerationResult | None = None
    error: str | None = None
