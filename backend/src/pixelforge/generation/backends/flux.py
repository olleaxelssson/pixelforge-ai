"""FLUX.1-schnell backend (Apache-2.0). Requires the ``[ml]`` extra and weights.

The pipeline is lazy-loaded on first use and cached for the process lifetime.
Device selection: CUDA → MPS → CPU (see models_manager.device).
"""

from __future__ import annotations

import logging
from typing import Any

from PIL import Image

from pixelforge.config import get_settings
from pixelforge.core.errors import BackendUnavailableError
from pixelforge.generation.backends.base import DiffusionSpec, GenerationBackend, ProgressFn
from pixelforge.models_manager.device import resolve_device

logger = logging.getLogger("pixelforge.flux")


class FluxSchnellBackend(GenerationBackend):
    name = "flux-schnell"

    def __init__(self) -> None:
        self._pipeline: Any = None

    def is_available(self) -> bool:
        try:
            import diffusers  # noqa: F401
            import torch  # noqa: F401
        except ImportError:
            return False
        return True

    def _load_pipeline(self) -> Any:
        if self._pipeline is not None:
            return self._pipeline
        if not self.is_available():
            raise BackendUnavailableError(
                "ML dependencies not installed. Install with: pip install 'pixelforge[ml]'"
            )
        import torch
        from diffusers import FluxPipeline

        settings = get_settings()
        device = resolve_device(settings.device)
        dtype = torch.bfloat16 if device != "cpu" else torch.float32
        logger.info("loading %s on %s (%s)", settings.flux_model_id, device, dtype)
        pipeline = FluxPipeline.from_pretrained(
            settings.flux_model_id,
            torch_dtype=dtype,
            cache_dir=settings.models_dir,
        )
        if device == "cuda":
            pipeline.enable_model_cpu_offload()
        else:
            pipeline = pipeline.to(device)
        self._pipeline = pipeline
        return pipeline

    def generate(self, spec: DiffusionSpec, on_progress: ProgressFn) -> list[Image.Image]:
        import torch

        pipeline = self._load_pipeline()
        generator = torch.Generator("cpu").manual_seed(spec.seed)

        def step_callback(pipe: Any, step: int, timestep: Any, kwargs: dict) -> dict:
            on_progress((step + 1) / spec.steps)
            return kwargs

        result = pipeline(
            prompt=spec.prompt,
            num_inference_steps=spec.steps,
            guidance_scale=0.0,  # schnell is guidance-distilled
            width=spec.resolution,
            height=spec.resolution,
            num_images_per_prompt=spec.batch_size,
            generator=generator,
            callback_on_step_end=step_callback,
        )
        return [img.convert("RGBA") for img in result.images]
