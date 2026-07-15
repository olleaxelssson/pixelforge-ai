# AI Model Research for Pixel Art Generation

Date: 2026-07-15 · Author: Devin (project architect) · Status: Adopted (see DECISIONS.md D-001)

## Constraints (from project requirements)

1. **Local-only inference**, fully offline, on consumer hardware (GPU with CPU fallback).
2. **Commercial-safe licensing** — Apache/MIT-style. Output must be usable in commercial games.
3. Native pixel-art quality at small target sizes (16×16 → 256×256): crisp pixels, limited
   palettes, readable silhouettes — not "low-resolution paintings".
4. Conditioning: text, reference image, sketch, palette; animation-frame consistency.

## Candidate Evaluation

| Model | License | Params | VRAM (fp16/bf16) | Steps | Pixel-art suitability | Verdict |
|---|---|---|---|---|---|---|
| **FLUX.1-schnell** | Apache-2.0 ✅ | 12B | ~24GB full; ~8–12GB w/ fp8 + offload | 1–4 (distilled) | Excellent prompt adherence; strong with pixel-art LoRAs | **Primary** |
| FLUX.1-dev | Non-commercial ❌ | 12B | — | 20–50 | Best-in-class | Rejected (license) |
| SDXL 1.0 | OpenRAIL++ ⚠️ | 3.5B | ~8GB | 20–40 | Huge pixel-art LoRA ecosystem; ControlNet mature | **Secondary/optional** |
| SD 1.5 | OpenRAIL ⚠️ | 0.9B | ~4GB | 20–40 | Many pixel checkpoints, dated quality | Rejected (quality) |
| SD 3 / 3.5 | Stability Community License ⚠️ | 2–8B | 6–18GB | 28+ | Good | Rejected (license terms gate >$1M revenue; weaker LoRA ecosystem) |
| PixArt-Σ | AGPL code / open weights | 0.6B | ~6GB | 20 | Decent, small ecosystem | Rejected (ecosystem) |
| Sana (NVIDIA) | Non-commercial weights ❌ | 0.6–4.8B | low | few | Fast | Rejected (license) |
| Pure pixel-art GANs/VAEs | varies | small | tiny | — | Limited diversity, poor prompt control | Rejected as primary; candidate for refinement stage |

Notes:
- **OpenRAIL++** (SDXL) permits commercial use but attaches use-based restrictions; it is not
  Apache/MIT-style. Given the hard constraint, SDXL is offered only as an *optional user-installed*
  backend, never bundled or required.
- **FLUX.1-schnell** is the only top-tier model with a genuine Apache-2.0 license. Its 1–4 step
  distillation also makes CPU fallback *practical* (minutes, not hours).

### Why raw diffusion output is not pixel art

All diffusion models natively emit ≥512px images with soft gradients and anti-aliased edges.
Generating directly at 16–256px is out-of-distribution and produces mush. Community consensus
(pixel-art LoRA workflows) is: generate at model-native resolution with a pixel-art style adapter,
then **snap to the target pixel grid** deterministically. Quality comes from the *combination*.

## Adopted Approach: Hybrid Pipeline

```
prompt/image/sketch ─► Stage A: Diffusion (FLUX.1-schnell + pixel-art LoRA,
                        model-native res, e.g. 1024×1024, 4 steps)
                    ─► Stage B: Pixelization (content-aware grid snap to target size,
                        nearest-dominant-color cell voting, edge-preserving)
                    ─► Stage C: Palette quantization (median-cut / user palette /
                        console preset; optional ordered dithering)
                    ─► Stage D: Cleanup (orphan-pixel removal, outline normalization,
                        optional 1px contrast outline, alpha binarization)
```

- **Stage A adapters**: pixel-art LoRAs trained in-project (training pipeline milestone) or
  user-imported. LoRA licensing is user's responsibility for imported files; bundled LoRAs will be
  trained on licensed/owned data.
- **Sketch conditioning**: ControlNet-style conditioning for FLUX (e.g. controlnet-union for FLUX,
  Apache-compatible implementations via diffusers) at Stage A; fallback = img2img with high
  structure preservation.
- **Animation consistency**: seed-anchored batch generation + shared palette lock (Stage C) +
  reference-frame img2img; later milestone adds explicit frame-interpolation conditioning.

### Hardware tiers

| Tier | Hardware | Config |
|---|---|---|
| High | ≥16GB VRAM | FLUX.1-schnell bf16, no offload, ~1–3 s/image |
| Mid | 8–12GB VRAM | fp8 quantized + sequential CPU offload, ~5–15 s |
| Low | Apple Silicon (MPS) | bf16 w/ attention slicing |
| Fallback | CPU only | quantized schnell 4-step, ~1–5 min/image; Stages B–D are always fast |

### Backend abstraction

The pipeline is implemented behind a `GenerationBackend` interface so models are swappable:
`FluxSchnellBackend` (default), `SDXLBackend` (optional, user-installed), `MockBackend`
(deterministic procedural output, used for tests/CI/UI development). Stages B–D are pure
image-processing and model-independent.

## Reasoning Summary

FLUX.1-schnell is chosen not for popularity but because it is the *only* candidate satisfying all
three hard constraints simultaneously: Apache-2.0 license, state-of-the-art prompt adherence, and
few-step inference that keeps local CPU fallback viable. The deterministic pixel-refinement stages
(B–D) are where pixel-art quality is actually enforced, which also de-risks the model choice:
swapping Stage A later requires no changes elsewhere.
