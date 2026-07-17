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

---

## Agentic layer (Phase 1) — full ADRs in `docs/adr/`

The following decisions design an agent-directed layer *above* the existing deterministic pipeline.
Each is a short index entry here; the long-form ADR (alternatives, benchmarks, complexity,
scalability, performance, maintainability, licensing, validation, repo mapping) is linked. Motivated
by `docs/research/agentic-pixel-art-research.md`. All are **Proposed** pending review, additive, and
must not regress the current pipeline or CI.

## D-009: Scene Graph as the central data contract
**Date:** 2026-07-16 · **Status:** Accepted (M7 foundation) · **ADR:** [docs/adr/D-009-scene-graph.md](docs/adr/D-009-scene-graph.md)

A versioned pydantic `SceneGraph` (`core/scene_graph.py`) is the single source of truth for a
generation: entity/parts/materials/palette-indexed colors/lighting/pose/camera/animation/provenance.
Agents write it, the pipeline compiles from it, the editor edits it. Enables edit-without-
regeneration and structurally defeats identity drift. Colors are palette indices; serialization is
canonical (hashable for caching/provenance); JSON Schema is exported for the frontend to mirror.

## D-010: Agent runtime & `PlanningBackend` interface
**Date:** 2026-07-16 · **Status:** Accepted (M7 foundation) · **ADR:** [docs/adr/D-010-agent-runtime-planning-backend.md](docs/adr/D-010-agent-runtime-planning-backend.md)

Single-responsibility agents emit validated JSON (Scene-Graph patches), orchestrated by a
lightweight in-house DAG — not a heavy framework. A `PlanningBackend` ABC mirrors `GenerationBackend`
(Anthropic/OpenAI/Ollama + a deterministic `MockPlanningBackend` for CI). Agents *plan and critique*;
deterministic code executes — avoiding Texel Studio's per-pixel-LLM scalability wall. A "fast path"
toggle skips planning and reproduces today's behavior.

## D-011: Character Memory (IP-Adapter-first, no drift)
**Date:** 2026-07-16 · **Status:** Accepted (M10: Tier 1) · **ADR:** [docs/adr/D-011-character-memory.md](docs/adr/D-011-character-memory.md)

Persisted `Character` = canonical Scene-Graph fragment + locked palette + reference frames + CLIP/
SigLIP identity embeddings. Tier 1 (default): IP-Adapter reference conditioning + palette lock + slot
reuse, no training. Tier 2 (optional): per-character LoRA. A measured drift gate (embedding cosine
threshold) rejects/regenerates on drift. Documented FLUX-IP-Adapter maturity fallback (img2img / SDXL).

## D-012: Palette Intelligence
**Date:** 2026-07-16 · **Status:** Accepted (M8) · **ADR:** [docs/adr/D-012-palette-intelligence.md](docs/adr/D-012-palette-intelligence.md)

Deterministic, model-free color math extending `palettes/`: ranking, WCAG + CIEDE2000 contrast,
CVD simulation (Machado/Brettel), readability, dedup, perceptual compression in CIELAB, and
actionable suggestions. Fully unit-testable, instant, high-value early milestone.

## D-013: Pixel QA engine & AI critic
**Date:** 2026-07-16 · **Status:** Accepted (M9: Layer 1) · **ADR:** [docs/adr/D-013-pixel-qa-and-critic.md](docs/adr/D-013-pixel-qa-and-critic.md)

Layer 1: deterministic defect detectors (orphans, clusters, jaggies, banding, pillow shading,
palette overflow, silhouette, dither, light direction) with typed findings + safe auto-repair.
Layer 2: a VLM+embedding critic scoring readability/palette/contrast/silhouette/consistency/quality,
masking failing regions for a bounded region-repair loop (K≤2). Both mockable; thresholds calibrated
against a golden set to avoid false rejects.

## D-014: Agent / Tool Plugin SDK
**Date:** 2026-07-16 · **Status:** Proposed · **ADR:** [docs/adr/D-014-agent-tool-plugin-sdk.md](docs/adr/D-014-agent-tool-plugin-sdk.md)

Standard Python entry points over the registry pattern let third parties add agents, tools, prompt
optimizers, exporters, tile/animation modules, palette analyzers, and QA detectors without editing
core. Semantically-versioned interfaces + a manifest + a loader; disabled-by-default trust model with
future subprocess/WASM isolation. Core stays MIT and works with zero plugins.
