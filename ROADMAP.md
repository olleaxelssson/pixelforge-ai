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
- ✅ (M18) 13 action templates → seed-anchored, palette-locked frame sequences; GIF + sprite-sheet
- ✅ (M18) Onion-skin + timeline preview in the UI; per-frame QA
- ✅ (M19) Reference-frame chaining (each frame img2img's from the previous; gated to real backends)
  + per-frame identity-consistency measurement (reuses the D-011 embedding gate), surfaced in the UI
- Export presets polish

## M4 — Training pipeline & dataset tools
- ✅ (M21) Dataset import, validation, duplicate detection (perceptual hash), corrupt-file detection
- ✅ (M21) Auto-captioning, kohya-style training manifest (JSONL) + LoRA config
- ✅ (M21) LoRA fine-tuning trainer wrapper (gated like FLUX); metadata/label editor, balancing later

## M5 — Editor & UX depth
- ✅ (M22) Seamless tiling (seam-blend) + live tiling preview; Wang/blob auto-tile export
- Dockable/multi-window layouts, advanced selection, palette editor v2
- Autosave/session recovery hardening, project templates
- ✅ (M20) Aseprite-compatible export (.aseprite writer)

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
- **Golden-image regression** (`tests/golden/` + `test_golden.py`): committed reference sprites per
  (prompt, mode, size, seed, palette). Always-on check asserts version-robust structure (shape,
  silhouette, palette budget) — the mock's float noise + Pillow median-cut aren't bit-reproducible
  across CPUs — with byte-exact matching gated behind `PIXELFORGE_STRICT_GOLDEN=1` on the authoring
  machine; `PIXELFORGE_UPDATE_GOLDEN=1` rewrites.
- **Benchmark harness** (`generation/benchmark.py`, `pixelforge benchmark`): runs a fixed suite,
  times each generation, and scores quality via the QA engine (D-013) — quality is measured, not
  asserted; reports device + peak VRAM when a GPU is present. Runs in CI against the mock.
- Needs real hardware to finish: actual FLUX inference, fp8/offload/VRAM numbers, ControlNet output
  quality. The code paths are in place and gated; only execution-on-GPU remains.

### M17 — Semantic critic for QA (D-013) ✅ (mock-verifiable parts)
- Completes the "critique" side with real *judgment*: does the sprite **read as** the intended
  subject, and is it appealing — beyond the pixel heuristics.
- `qa/critic_backends/` (swappable, mirrors the generation backends): deterministic
  `MockCriticBackend` (runs in CI; `appeal` is a real palette-readability signal, `subject_match` a
  deterministic subject+image proxy) and a **gated** `VLMCriticBackend` (transformers/torch, prompts
  a vision-language model for a JSON assessment; defensively parsed). Chosen via a registry.
- `VLMCritic` implements the existing `Critic` interface (new `Critic.evaluate()` returns scores +
  an optional `Critique`), reuses `HeuristicCritic` for the pixel axes, and **folds subject-match/
  appeal into `overall`** — so the M15 repair loop (accepts only on a higher overall) optimizes for
  "reads as the subject" too.
- Opt-in via `qa_critic=vlm` (+ `vlm_critic_backend`); `subject` threaded through the pipeline,
  `POST /api/qa`, and `pixelforge qa --subject --critic vlm`. Surfaced in the QA tab as a critique
  block (verdict + subject-match/appeal meters + notes). New `pixelforge.critic_backends` plugin group.
- Later: run a real VLM (needs the `[ml]` extra + a model + a GPU); the path is in place and gated.

### M18 — Animation: seed-anchored, palette-locked frame sequences (M3, D-009) ✅
- Turns an action (13 templates in `animation/actions.py`) into a real multi-frame sprite sequence
  via `animation/sequence.py` (`AnimationSequence`), reusing the generation pipeline per frame.
- **Seed anchoring** — every frame shares one seed; only the per-frame action description changes.
  **Palette lock** — frame 1's palette is reused for all later frames (new
  `GenerationRequest.locked_palette_hex`, reusing the D-012/M8 lock), so colors never drift.
- Each frame optionally runs through the QA engine (D-013); frames assemble into a looping **GIF**
  and a **sprite sheet** (`animation/assembly.py`).
- `POST /api/animation/generate` + `GET /api/animation/actions`; `pixelforge animate` + `list actions`.
- **Animation tab** in the UI: action picker, frame-duration slider, an animated stage with
  **play/pause** + **onion-skin**, a clickable timeline, the locked palette, and GIF/sheet downloads.
- Pure `playback.ts` (nextFrame/onionFrame) unit-tested; browser E2E of the whole tab.

### M19 — Cross-frame consistency: reference chaining + drift measurement (M3 finish, D-009×D-011) ✅
- **Reference chaining** (`AnimationRequest.reference_chaining`): each frame is fed the *previous*
  frame as a Stage-A reference (`GenerationRequest.reference_image_base64` → `DiffusionSpec`), so a
  real img2img backend evolves poses from a shared anchor. No-op on the mock (it ignores references),
  so seed-anchoring + palette-lock are unchanged — verified with a spy backend.
- **Per-frame identity consistency** (`check_consistency`): embeds each frame (reusing the D-011/M10
  `EmbeddingBackend`), measures cosine similarity to frame 1 (the anchor), and flags frames below the
  drift threshold — fully deterministic on the mock. `mean/min_consistency` + a `consistent` verdict.
- `pixelforge animate --reference-chain --consistency`; the Animation tab gains both toggles, a
  per-frame consistency badge on the timeline, and a mean/min consistency line. Pure
  `consistencyBadge` unit-tested; browser E2E confirmed the readout.
- Later: run a real img2img backend so reference chaining actually raises the consistency numbers.

### M20 — Aseprite-compatible export (M5, D-001) ✅
- `exporters/aseprite.py`: a pure `build_aseprite(frames)` serializer writing the documented
  `.aseprite` binary (indexed 8bpp, one layer, cels per frame, palette from the frames) so a
  generated animation round-trips into Aseprite. `AsepriteExporter` registers into the exporter
  registry, so `pixelforge export --format aseprite`, `POST /api/export`, and the export catalog
  pick it up automatically.
- **Cels are written uncompressed** (type 0) → byte-deterministic across machines (no zlib version
  dependency), so a real **byte-exact golden test** runs in CI; structure is also verified by a
  `parse_aseprite` round-trip that reconstructs every original frame from the indexed cels.
- Wired into the UI: a **download .aseprite** button in the Animation tab's export block (posts the
  frame filenames to `/api/export`); CORS now exposes `Content-Disposition` so the filename is kept.

### M21 — Dataset & LoRA-training toolkit (M4, D-001) ✅
- New `dataset/` subsystem — the training-data half of "AI-native". `build_dataset` is a pure,
  deterministic pipeline: **validate** (corrupt-file detection, <8px rejected, oversize/non-square
  flagged) → **dedup** (perceptual difference-hash + greedy Hamming clustering) → **caption**
  (reuses the D-012 palette intelligence: size, palette size, dominant hue family, frame fill — no
  model) → emit a kohya/HF **`manifest.jsonl`** + a **`lora_config.json`**. Near-duplicates are
  excluded from the manifest so the training set stays clean.
- The dHash resizes with **NEAREST** (no interpolation) so hashes are bit-identical across machines,
  keeping the dedup deterministic in CI. Note: flat single-color images all collapse to the same
  hash — real sprites have internal structure, so this is a non-issue in practice.
- `LoraTrainer` mirrors the FLUX gate: `is_available()` checks for the torch/PEFT stack, `train()`
  raises `BackendUnavailableError` without it, and a pure `training_plan()` returns the kohya
  `sd-scripts` command line (testable without a GPU).
- Surfaced as `pixelforge dataset build <dir> [-o out]` (scans a folder, prints the report as JSON,
  optionally writes the manifest + config) and `POST /api/dataset` (analyzes base64 uploads in
  memory). New **Dataset** tab: multi-file upload → summary counts, per-image validation table with
  trainable/duplicate/invalid badges, duplicate clusters, and manifest + config previews.

### M22 — Seamless tiling & auto-tile export (M5, D-001) ✅
- `generation/tileize.py`: a pure, deterministic **wrap-aware edge blend** (`make_tileable`). Within
  a band on each side, every pixel is cross-mixed with its wrap-neighbour on the opposite edge,
  weighted so the mix is exactly half-half at the very edge — making the two edges **identical** so
  the seam vanishes — and fading to zero toward the interior (the middle is untouched). Horizontal
  then vertical passes also converge the four corners, so corner-to-corner tiling is seamless too.
- Opt-in via a `tileable` request flag. Applied **before** palette quantization in the pipeline, so
  the blended edge colours snap back onto the locked palette while staying equal on both sides
  (equal RGB quantizes to the same index) — on-palette *and* seamless after quantization.
- **Seam-discontinuity QA detector** (`qa/detectors/seam.py`): measures the edge-wrap difference and
  warns on a visible seam; only fires for sprites meant to tile (`DetectorContext.tileable`) and
  feeds the existing QA engine. `seam_metrics`/`seam_score` are shared with the pipeline.
- **Wang/blob auto-tile exporter** (`exporters/wang_blob.py`): builds the standard **47-tile blob
  set** from one base tile by carving a border band off each disconnected side and rounding inner
  corners. The 47 comes from the blob rule (a corner counts only when both its adjacent edges do),
  which collapses 256 raw neighbour configs to 47. Emits the sheet + a JSON bitmask-to-cell map.
- Surfaced as `pixelforge generate --tileable`, `pixelforge export --format wang-blob`, a `tileable`
  flag on the generate/QA endpoints, and a **live tiling preview** in the Generate tab: a 3x3 repeat
  with a seamlessness readout, computed client-side by the pure `tileView.ts` `seamScore`
  (unit-tested). Browser E2E confirmed a "100% seamless" preview.
