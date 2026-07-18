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
- ✅ (M16) FLUX.1-schnell integration hardening: fp8 quantization path, CPU offload tiers
- ✅ (M16) ControlNet conditioning on the silhouette control map (M11); benchmark suite + golden regression
- In-house pixel-art LoRA training + bundled LoRA
- Image→pixel-art img2img; model download UI
- (Real-GPU-only pieces of M16 — actual FLUX inference, VRAM numbers — need weights + a GPU)

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
- Layer 2 (region-repair loop) landed in **M15**; a VLM critic is the remaining follow-up

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

### M13 — Surface the agentic layer in the UI (D-009…D-013) ✅
- The M7–M12 backend was CLI/API-only; M13 brings it into the Electron/React app as new nav views
- **Plan preview** inline in Generate (`POST /api/plan`): Scene Graph summary (subject, parts,
  materials, composition, lighting, palette), silhouette occupancy grid, compiled prompt, agent trace
- **QA** view (`POST /api/qa`): load a recent result or an uploaded PNG, deterministic detectors →
  score bars + severity-ranked findings, one-click "apply safe repairs", open the repair in the editor
- **Characters** view (`/api/characters`): list/create, add reference frames (passport anchors the
  identity embedding), cosine-similarity drift meter against a sprite
- **Palette Lab** view (`/api/palettes/{id}/analysis`): readability/contrast/ΔE metrics, suggestions,
  shading ramps, near-duplicate detection, color-vision-deficiency simulation
- Pure view helpers (`planView.ts`, `qaView.ts`) unit-tested; typed API client + image↔base64 helpers;
  verified end-to-end in a real browser (Playwright) against the live backend, zero console errors
- Later: extension slots for plugin-contributed panels/tools (depends on M12's FE-slot follow-up)

### M14 — Character-aware generation loop in the UI (D-011) ✅
- Ties the M13 surfaces into one workflow: generate as a character → drift-check the result → QA it
- **Generate as character** selector in the Generate panel: sets `character_id` so the backend prepends
  the identity phrase, forces character mode, locks the palette, and rides the canonical frame as a
  Stage-A reference; the typed prompt becomes the *variation* (e.g. "winter armor")
- Characters panel: **check drift against a recent generation result** (not just an uploaded file),
  closing the generate→verify loop in one place
- QA panel: a **character reference frame** as a third sprite source
- Pure `recentResults.ts` helper (shared by QA + Characters), unit-tested; browser E2E of the whole
  loop (generate → 95% consistent drift → QA source) with zero console errors

### M15 — Close the critique loop: QA-gated repair loop (D-013 Layer 2) ✅
- The "critique" half the architecture is named for: after QA, **regenerate only the failing
  regions** and re-score, accepting a candidate only when the overall score *strictly improves* and
  no new errors appear. Bounded (`max_iterations`) and monotonic → always terminates.
- `qa/repair_loop.py`: `RepairLoop` + a swappable `RegionRegenerator` — `DeterministicInpaintRegenerator`
  (median denoise + palette snap, mask-scoped, runs in CI) and `BackendRegionRegenerator` (the real
  img2img-on-the-crop path via a `GenerationBackend`, works with the mock too). Only masked pixels change.
- Wired behind `qa_repair_loop` (pipeline), `POST /api/qa {repair_loop:true}`, and
  `pixelforge qa --repair-loop`; exposed in the QA tab as **"Regenerate failing regions"** with a
  per-iteration report (before→after score, accepted/rejected).
- Tests: convergence (noisy sprite cleaned, score up), non-improving candidate rejected, mask
  discipline, backend-regenerator path on the mock backend, API + CLI. Browser E2E: a noisy upload
  went 48% → 83% (PASS) in one accepted iteration.
- Later: a VLM-backed `Critic` (same interface) for perceptual/semantic scoring beyond the heuristics.

### M16 — Real-model quality pass (M2, D-002) ✅ (mock-verifiable parts)
- FLUX backend hardened behind the `GenerationBackend` interface: **fp8** weight quantization
  (optimum.quanto), **CPU-offload tiers** (`none`/`model`/`sequential`, `auto` by device), and a
  **ControlNet** path that consumes the M11 silhouette control map (`spec.extra["silhouette_map"]`).
- The FLUX *decisions* (dtype/offload/fp8/ControlNet routing) live in torch-free `flux_config.py`
  and are fully unit-tested; the torch/diffusers calls stay behind `is_available()` (no GPU in CI).
- **Golden-image regression** (`tests/golden/` + `test_golden.py`): the deterministic mock pipeline
  is pixel-locked per (prompt, mode, size, seed, palette); `PIXELFORGE_UPDATE_GOLDEN=1` rewrites.
- **Benchmark harness** (`generation/benchmark.py`, `pixelforge benchmark`): runs a fixed suite,
  times each generation, and scores quality via the QA engine (D-013) — quality is measured, not
  asserted; reports device + peak VRAM when a GPU is present. Runs in CI against the mock.
- Needs real hardware to finish: actual FLUX inference, fp8/offload/VRAM numbers, ControlNet output
  quality. The code paths are in place and gated; only execution-on-GPU remains.
