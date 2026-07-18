"""FLUX configuration decisions (M2, D-002) — pure and torch-free, so they run in CI.

The real backend (:mod:`flux`) can only run with the ``[ml]`` extra + weights + a GPU, none of
which exist in CI. To keep the *decision logic* — which dtype, which CPU-offload tier, whether to
route through ControlNet — testable, it lives here as plain functions and maps to strings. The
backend translates those strings into torch/diffusers calls behind its availability gate.
"""

from __future__ import annotations

from pixelforge.generation.backends.base import DiffusionSpec

# The extra key the plan compiler sets with the silhouette control map (M11).
SILHOUETTE_MAP_KEY = "silhouette_map"

_VALID_QUANTIZATION = ("none", "fp8")
_VALID_OFFLOAD = ("auto", "none", "model", "sequential")


def resolve_dtype(device: str, quantization: str) -> str:
    """Return the torch dtype *name* for a device/quantization combo.

    CPU can't do half precision reliably → float32. fp8 is a weight-quantization request handled
    separately (see :func:`wants_fp8`); the compute dtype it runs under is still bfloat16 on GPU.
    """
    if device == "cpu":
        return "float32"
    return "bfloat16"


def wants_fp8(device: str, quantization: str) -> bool:
    """fp8 weight quantization is only meaningful on GPU and only when explicitly requested."""
    return quantization == "fp8" and device != "cpu"


def resolve_offload(device: str, offload: str) -> str:
    """Pick a CPU-offload tier: ``none`` | ``model`` | ``sequential``.

    ``auto`` keeps weights resident on CUDA-class GPUs (fastest) but offloads per-module on CPU/MPS
    where VRAM/RAM is the binding constraint. Explicit settings always win.
    """
    if offload not in _VALID_OFFLOAD:
        offload = "auto"
    if offload != "auto":
        return offload
    if device == "cuda":
        return "model"
    if device == "mps":
        return "sequential"
    return "none"  # cpu: nothing to offload to


def wants_controlnet(spec: DiffusionSpec, controlnet_id: str) -> bool:
    """Route through ControlNet only when a net is configured AND a control map is present."""
    return bool(controlnet_id) and spec.extra.get(SILHOUETTE_MAP_KEY) is not None


def normalize_quantization(value: str) -> str:
    return value if value in _VALID_QUANTIZATION else "none"
