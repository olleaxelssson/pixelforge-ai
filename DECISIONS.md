# Architectural Decision Records

## D-001: FLUX.1-schnell as primary generation model
**Date:** 2026-07-15 · **Status:** Accepted

Local-only inference + Apache/MIT-style licensing are hard constraints. FLUX.1-schnell is the only
state-of-the-art model with a true Apache-2.0 license, and its 4-step distillation makes CPU
fallback viable. SDXL (OpenRAIL++) is optional/user-installed only; FLUX.1-dev rejected
(non-commercial). Full analysis: `docs/research/model-research.md`.

## D-002: Hybrid pipeline (diffusion + deterministic pixel refinement)
**Date:** 2026-07-15 · **Status:** Accepted

Diffusion output at native resolution is never true pixel art. The pipeline is
diffusion (Stage A) → grid snap (B) → palette quantization (C) → cleanup (D). Stages B–D are pure,
deterministic image processing: they enforce pixel-art quality, are unit-testable without weights,
and make Stage A swappable.

## D-003: Two-process architecture (Electron/React UI + Python FastAPI backend)
**Date:** 2026-07-15 · **Status:** Accepted (user-selected)

ML ecosystem is Python; rich editor UI is best served by web tech. Electron main process spawns
and supervises the backend on localhost. HTTP for commands, WebSocket for progress streaming.
Trade-off: two runtimes to package; accepted for developer velocity and AI-assistant readability.

## D-004: Mock generation backend as first-class citizen
**Date:** 2026-07-15 · **Status:** Accepted

`MockBackend` produces deterministic procedural images (seeded). Enables: CI without GPU/weights,
frontend development offline, reproducible tests of Stages B–D and the full API. Selected
automatically when ML extras are not installed, or via `PIXELFORGE_BACKEND=mock`.

## D-005: Data-driven styles, modes, and palettes
**Date:** 2026-07-15 · **Status:** Accepted

Styles, generation modes, and palettes are data (TOML/JSON) loaded by registries, not code.
Users and future AI agents can extend them without touching the pipeline. Retro-console palettes
are *inspired-by* approximations, never copied assets.

## D-006: Async in-process job queue (no external broker)
**Date:** 2026-07-15 · **Status:** Accepted

Single-user desktop app → asyncio queue with one GPU worker, cancellation, and progress events.
Redis/Celery would add deployment burden with no benefit. Revisit only if multi-machine render
farms become a goal.

## D-007: Undo/redo via immutable pixel-buffer snapshots
**Date:** 2026-07-15 · **Status:** Accepted

Editor layers are `Uint8ClampedArray` buffers; history stores copy-on-write snapshots capped by
memory budget. Simpler and more robust than command-pattern inversion for pixel editing at ≤256².

## D-008: MIT license for project code
**Date:** 2026-07-15 · **Status:** Accepted

Maximizes reuse and matches the commercial-safe constraint. Model weights remain under their own
licenses (FLUX.1-schnell: Apache-2.0); the app downloads weights at first run rather than bundling.
