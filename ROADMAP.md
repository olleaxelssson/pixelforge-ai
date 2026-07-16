# Roadmap

## M1 — Foundation (this phase) ✅
- Repo structure, docs (ARCHITECTURE, DECISIONS, CONTRIBUTING, research)
- Backend: config, logging, FastAPI app, async job queue with cancellation/progress
- Generation pipeline with `GenerationBackend` abstraction; `MockBackend`; FLUX backend (requires `[ml]` extra + weights)
- Pixelization stage (grid snap), palette system (presets, extraction, quantization, dithering, import/export)
- Style presets (12) and generation modes (15), data-driven registries
- Exporters: PNG, GIF, sprite sheet, texture atlas JSON, Unity/Godot/Unreal layouts
- Frontend: Electron + React shell, dark theme, generation panel, queue/results, settings
- Pixel editor v1: pencil/eraser/fill/line/rect/ellipse/select/move, layers, grid, zoom, undo/redo
- Tests (pytest + vitest), lint (ruff/mypy/eslint/tsc), GitHub Actions CI

## M2 — Real-model quality pass
- FLUX.1-schnell integration hardening: fp8 quantization path, CPU offload tiers, model download UI
- In-house pixel-art LoRA training + bundled LoRA
- Sketch conditioning (ControlNet-union for FLUX), image→pixel-art img2img
- Benchmark suite (speed, VRAM, output quality metrics) + golden-image regression tests

## M3 — Animation
- 13 action templates, seed-anchored frame batches, palette-locked sequences
- Onion skinning + timeline polish, GIF/sprite-sheet preview and export presets
- Reference-frame conditioning for cross-frame consistency

## M4 — Training pipeline & dataset tools
- Dataset import, validation, duplicate detection (perceptual hash), corrupt-file detection
- Auto-captioning, metadata/label editor, balancing, style tagging
- LoRA fine-tuning on consumer hardware (kohya-style trainer wrapper), training queue

## M5 — Editor & UX depth
- Dockable/multi-window layouts, tile preview (seamless mode), advanced selection, palette editor v2
- Autosave/session recovery hardening, project templates
- Aseprite-compatible export (.ase/.aseprite writer)

## M6 — Extensibility & release
- Plugin API (Python entry points + frontend extension slots)
- Packaging: Windows/macOS/Linux installers (electron-builder + bundled Python runtime)
- Performance profiling, memory budgets, resumable jobs across restarts
- User guide completion, troubleshooting matrix, v1.0 release

## Agentic pixel-art layer (M7+) — Phase 1 designed, implementation gated on review

A planning-and-critique agent layer over the existing deterministic pipeline. Research:
[docs/research/agentic-pixel-art-research.md](docs/research/agentic-pixel-art-research.md).
Per-subsystem ADRs: [docs/adr/](docs/adr/) (D-009…D-014). Every milestone below is **additive,
flag-gated, mock-tested, and must not regress the current pipeline or CI**. Sequencing puts the
cheapest/most-decoupled value first and freezes plugin interfaces last.

### M7 — Scene Graph + agent runtime foundation (D-009, D-010) ✅
- `core/scene_graph.py` (versioned pydantic, canonical hashing, migration hook, JSON-Schema export)
- `PlanningBackend` interface + deterministic `MockPlanningBackend`; `Agent` base, registry, DAG runtime
- Intent + Art Director agents → `generation/plan_compiler.py` compiling the Scene Graph into prompts
- Opt-in via `planning_enabled` (fast path unchanged by default); `POST /api/plan`, `pixelforge plan`
- End-to-end on the mock backend, fully tested (ruff/mypy/pytest green); no pipeline regression

### M8 — Palette Intelligence (D-012)
- Deterministic color math: ranking, WCAG + CIEDE2000 contrast, CVD simulation, readability, dedup,
  compression, suggestions; API + palette-panel surfacing (high value, low risk, no models)

### M9 — Pixel QA engine (D-013)
- Deterministic defect detectors + safe auto-repair; `MockCritic`; bounded region-repair loop
- Golden-set threshold calibration; QA findings stored on the Scene Graph

### M10 — Character Memory (D-011)
- Character store + reference frames + identity embeddings; IP-Adapter Tier-1 path + palette lock
- Measured drift gate feeding the QA loop; "Elias winter armor / without helmet" scenario tests

### M11 — Full planning agent set + provenance
- Composition / Silhouette / Lighting / Material / Animation planners; provenance sidecar per asset
- Silhouette/pose → ControlNet conditioning; cross-frame consistency for animation

### M12 — Plugin SDK & marketplace architecture (D-014)
- Entry-point plugin loader + manifest; stabilized, versioned extension interfaces; sample plugins
- Developer docs (contracts, versioning, security); frontend extension slots
