"""Compute-device selection: CUDA → MPS → CPU."""

from __future__ import annotations


def resolve_device(preference: str = "auto") -> str:
    if preference != "auto":
        return preference
    try:
        import torch
    except ImportError:
        return "cpu"
    if torch.cuda.is_available():
        return "cuda"
    if getattr(torch.backends, "mps", None) is not None and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def device_info() -> dict[str, object]:
    info: dict[str, object] = {"device": resolve_device(), "cuda": False, "mps": False}
    try:
        import torch
    except ImportError:
        return info
    info["cuda"] = torch.cuda.is_available()
    if info["cuda"]:
        info["gpu_name"] = torch.cuda.get_device_name(0)
        info["vram_gb"] = round(torch.cuda.get_device_properties(0).total_memory / 1e9, 1)
    info["mps"] = (
        getattr(torch.backends, "mps", None) is not None and torch.backends.mps.is_available()
    )
    return info
