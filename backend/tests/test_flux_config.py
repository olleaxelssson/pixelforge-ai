"""FLUX config-decision tests (M2, D-002).

The real FLUX backend needs a GPU + weights and never runs in CI, but its *decisions* — dtype,
CPU-offload tier, fp8, ControlNet routing — are pure functions and are fully tested here.
"""

from __future__ import annotations

from PIL import Image

from pixelforge.generation.backends.base import DiffusionSpec
from pixelforge.generation.backends.flux_config import (
    SILHOUETTE_MAP_KEY,
    normalize_quantization,
    resolve_dtype,
    resolve_offload,
    wants_controlnet,
    wants_fp8,
)


def test_dtype_is_float32_on_cpu_bf16_on_gpu() -> None:
    assert resolve_dtype("cpu", "none") == "float32"
    assert resolve_dtype("cuda", "none") == "bfloat16"
    assert resolve_dtype("mps", "fp8") == "bfloat16"


def test_fp8_only_when_requested_and_on_gpu() -> None:
    assert wants_fp8("cuda", "fp8") is True
    assert wants_fp8("cpu", "fp8") is False
    assert wants_fp8("cuda", "none") is False


def test_offload_auto_picks_tier_by_device() -> None:
    assert resolve_offload("cuda", "auto") == "model"
    assert resolve_offload("mps", "auto") == "sequential"
    assert resolve_offload("cpu", "auto") == "none"


def test_offload_explicit_setting_wins() -> None:
    assert resolve_offload("cuda", "sequential") == "sequential"
    assert resolve_offload("cuda", "none") == "none"
    assert resolve_offload("cuda", "bogus") == "model"  # invalid -> auto -> cuda default


def test_controlnet_needs_both_a_net_and_a_control_map() -> None:
    plain = DiffusionSpec(prompt="x")
    with_map = DiffusionSpec(prompt="x", extra={SILHOUETTE_MAP_KEY: Image.new("L", (8, 8))})
    assert wants_controlnet(plain, "some/controlnet") is False  # no control map
    assert wants_controlnet(with_map, "") is False  # no net configured
    assert wants_controlnet(with_map, "some/controlnet") is True


def test_normalize_quantization() -> None:
    assert normalize_quantization("fp8") == "fp8"
    assert normalize_quantization("none") == "none"
    assert normalize_quantization("int4") == "none"
