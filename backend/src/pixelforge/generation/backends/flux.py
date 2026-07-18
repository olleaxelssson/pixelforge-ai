"""FLUX.1-schnell backend (Apache-2.0). Requires the ``[ml]`` extra + weights + a GPU.

The pipeline is lazy-loaded on first use and cached for the process lifetime. Device selection:
CUDA → MPS → CPU (see ``models_manager.device``). Quality knobs (M2, D-002) — fp8 weight
quantization, CPU-offload tiers, and ControlNet conditioning on the silhouette control map (M11) —
are decided by the torch-free helpers in :mod:`flux_config` and applied behind ``is_available``.
"""

from __future__ import annotations

import logging
from typing import Any

from PIL import Image

from pixelforge.config import get_settings
from pixelforge.core.errors import BackendUnavailableError
from pixelforge.generation.backends.base import DiffusionSpec, GenerationBackend, ProgressFn
from pixelforge.generation.backends.flux_config import (
    SILHOUETTE_MAP_KEY,
    normalize_quantization,
    resolve_dtype,
    resolve_offload,
    wants_controlnet,
    wants_fp8,
)
from pixelforge.models_manager.device import resolve_device

logger = logging.getLogger("pixelforge.flux")


class FluxSchnellBackend(GenerationBackend):
    name = "flux-schnell"

    def __init__(self) -> None:
        self._pipeline: Any = None
        self._uses_controlnet = False

    def is_available(self) -> bool:
        try:
            import diffusers  # noqa: F401
            import torch  # noqa: F401
        except ImportError:
            return False
        return True

    def _torch_dtype(self, name: str) -> Any:
        import torch

        return {"bfloat16": torch.bfloat16, "float32": torch.float32}[name]

    def _apply_fp8(self, pipeline: Any) -> None:
        """Quantize the transformer to fp8 weights via optimum.quanto, if installed."""
        try:
            from optimum.quanto import freeze, qfloat8, quantize
        except ImportError:
            logger.warning(
                "flux_quantization=fp8 requested but optimum.quanto is unavailable; "
                "install 'pixelforge[ml]' extras. Continuing in bf16."
            )
            return
        logger.info("quantizing FLUX transformer to fp8 (optimum.quanto)")
        quantize(pipeline.transformer, weights=qfloat8)
        freeze(pipeline.transformer)

    def _load_pipeline(self, spec: DiffusionSpec) -> Any:
        settings = get_settings()
        use_controlnet = wants_controlnet(spec, settings.flux_controlnet_id)
        # Reload only if the ControlNet requirement changed since the cached build.
        if self._pipeline is not None and self._uses_controlnet == use_controlnet:
            return self._pipeline
        if not self.is_available():
            raise BackendUnavailableError(
                "ML dependencies not installed. Install with: pip install 'pixelforge[ml]'"
            )

        device = resolve_device(settings.device)
        quantization = normalize_quantization(settings.flux_quantization)
        dtype = self._torch_dtype(resolve_dtype(device, quantization))
        offload = resolve_offload(device, settings.flux_offload)
        logger.info(
            "loading %s on %s (%s, offload=%s, controlnet=%s)",
            settings.flux_model_id,
            device,
            dtype,
            offload,
            use_controlnet,
        )

        pipeline = self._build_pipeline(settings, dtype, use_controlnet)
        if wants_fp8(device, quantization):
            self._apply_fp8(pipeline)
        self._place_pipeline(pipeline, device, offload)

        self._pipeline = pipeline
        self._uses_controlnet = use_controlnet
        return pipeline

    def _build_pipeline(self, settings: Any, dtype: Any, use_controlnet: bool) -> Any:
        from diffusers import FluxPipeline

        if use_controlnet:
            from diffusers import FluxControlNetModel, FluxControlNetPipeline

            controlnet = FluxControlNetModel.from_pretrained(
                settings.flux_controlnet_id, torch_dtype=dtype, cache_dir=settings.models_dir
            )
            return FluxControlNetPipeline.from_pretrained(
                settings.flux_model_id,
                controlnet=controlnet,
                torch_dtype=dtype,
                cache_dir=settings.models_dir,
            )
        return FluxPipeline.from_pretrained(
            settings.flux_model_id, torch_dtype=dtype, cache_dir=settings.models_dir
        )

    def _place_pipeline(self, pipeline: Any, device: str, offload: str) -> None:
        if offload == "sequential":
            pipeline.enable_sequential_cpu_offload()
        elif offload == "model":
            pipeline.enable_model_cpu_offload()
        else:
            pipeline.to(device)

    def generate(self, spec: DiffusionSpec, on_progress: ProgressFn) -> list[Image.Image]:
        import torch

        settings = get_settings()
        pipeline = self._load_pipeline(spec)
        generator = torch.Generator("cpu").manual_seed(spec.seed)

        def step_callback(pipe: Any, step: int, timestep: Any, kwargs: dict) -> dict:
            on_progress((step + 1) / spec.steps)
            return kwargs

        kwargs: dict[str, Any] = dict(
            prompt=spec.prompt,
            num_inference_steps=spec.steps,
            guidance_scale=0.0,  # schnell is guidance-distilled
            width=spec.resolution,
            height=spec.resolution,
            num_images_per_prompt=spec.batch_size,
            generator=generator,
            callback_on_step_end=step_callback,
        )
        if wants_controlnet(spec, settings.flux_controlnet_id):
            control = spec.extra[SILHOUETTE_MAP_KEY]
            assert isinstance(control, Image.Image)
            kwargs["control_image"] = control.convert("RGB")
            kwargs["controlnet_conditioning_scale"] = settings.flux_controlnet_scale

        result = pipeline(**kwargs)
        return [img.convert("RGBA") for img in result.images]
