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

### M8 — Palette Intelligence (D-012) ✅
- Deterministic color math (`palettes/color_math.py`): sRGB↔Lab, WCAG contrast, CIEDE2000, Machado CVD
- Analysis (`palettes/analysis.py`): ranking, ramps, near-duplicate detection, CVD confusion,
  perceptual compression (k-means in Lab), readability score, actionable suggestions
- `PaletteService.analyze`; `/api/palettes/{analyze,compress,simulate-cvd,{id}/analysis}`; `pixelforge palette`
- Validated against known references (WCAG 21:1, CIEDE2000 Sharma dataset); ruff/mypy/pytest green

### M9 — Pixel QA engine (D-013) ✅ (Layer 1)
- Deterministic detectors (`qa/detectors/`): floating pixels, broken clusters, palette overflow,
  silhouette, pillow shading, light-direction — with safe auto-repair for the first three
- Deterministic `HeuristicCritic` (reuses D-012) + `QAEngine` (run/repair); findings on the Scene Graph
- Opt-in pipeline hook (`qa_enabled`); `POST /api/qa`; `pixelforge qa` (`--repair`); all detectors tested
- Later: Layer-2 VLM critic and the diffusion region-repair loop (regenerate only failing regions)

### M10 — Character Memory (D-011) ✅ (Tier 1)
- `memory/`: `Character` (identity fragment + locked palette + reference frames + embedding),
  `CharacterStore` (JSON + frame PNGs), swappable `EmbeddingBackend` (deterministic mock)
- `CharacterMemory`: identity application (stable prompt prefix, palette lock, canonical frame as
  reference image) + measured cosine-similarity drift gate; "Elias winter armor" scenario tested
- `character_id` on `GenerationRequest`; `/api/characters` (CRUD/frames/drift); `pixelforge character`
- Later: IP-Adapter conditioning at Stage A (today: img2img reference fallback), Tier-2 LoRA,
  CLIP/SigLIP embedding backend

### M11 — Full planning agent set + provenance (D-009 v2, D-010) ✅
- Composition / Silhouette / Lighting / Material / Animation planners (7-agent pipeline total),
  folded into the Scene Graph by the runtime; trimmed registries still assemble
- Scene Graph v2: composition, silhouette occupancy grid, material finish hints, rim light —
  with a real v1→v2 migration exercising the versioning machinery
- Silhouette plan → Stage-A control map (`compile_silhouette_map` → `DiffusionSpec.extra`),
  ready for ControlNet conditioning when a real backend consumes it
- Provenance sidecar per asset (`*.provenance.json`: scene graph + prompts + seed + versions)
  whenever planning is active
- Later: cross-frame animation consistency (M3 reference-frame work)

### M12 — Plugin SDK & marketplace architecture (D-014) ✅
- Entry-point plugin loader (`plugins/loader.py`) + required `PluginManifest`; discovers `pixelforge.*`
  groups across installed distributions, validates, and registers into existing registries
- Six versioned extension interfaces: agents, exporters, QA detectors, generation backends,
  planning backends, embedding backends — each with a `register_*` hook; new groups are table-driven
- Semver plugin API (`PLUGIN_API_VERSION = "1.0"`): major mismatch refused, newer minor warns
- Trust model: disabled by default, explicit allowlist, per-component failure isolation, idempotent
  load; surfaced at `GET /api/plugins` and `pixelforge list plugins`
- Working sample `examples/plugins/pixelforge-hello` (ASCII exporter + checkerboard-noise detector)
  and developer guide `docs/developer/plugins.md`; injectable discovery keeps tests hermetic
- Later: frontend extension slots (panels/tools), subprocess/WASM isolation for untrusted plugins
