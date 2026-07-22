# CLAUDE.md — Working on PixelForge AI

PixelForge is an AI-native pixel art generator: Python FastAPI backend (generation
pipeline, palettes, styles, exporters, job queue) + Electron/React frontend
(generation UI, integrated pixel editor). Read `ARCHITECTURE.md` for subsystem
details, `DECISIONS.md` for why things are the way they are, `ROADMAP.md` for
what's next, and `CONTRIBUTING.md` for conventions.

## Setup

```bash
./scripts/setup.sh                 # one-shot: venv, deps, checks (both halves)
# or manually:
cd backend && python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
cd frontend && npm install
```

Optional real inference (GPU recommended, ~24 GB weights on first run):
`pip install -e ".[ml]"`. Without it, the deterministic **mock backend** is used
automatically — same pipeline, procedural sprites — so everything is testable
on any machine.

## Generate pixel art from the command line (no server, no GUI)

The `pixelforge` CLI is the primary interface for coding agents. All output is
JSON on stdout; progress goes to stderr.

```bash
cd backend
.venv/bin/pixelforge generate "a knight with a flaming sword" \
    --mode character --size 32 --seed 42 --batch 2 -o /tmp/sprites
.venv/bin/pixelforge generate "health potion" --mode item \
    --palette 8bit-console --dither ordered -o /tmp/sprites
.venv/bin/pixelforge generate "mossy stone floor" --mode tileset --tileable -o /tmp/sprites  # seam-blended, tiles seamlessly
.venv/bin/pixelforge tileset "grass field" --variants 4 --seed 5 -o /tmp/tiles  # coherent seam-locked terrain family + 47-tile blob sheet
.venv/bin/pixelforge export /tmp/sprites/cli_0.png --format unity --scale 4 -o /tmp/export   # also: aseprite, wang-blob, godot-tileset, tiled-tileset, gif, sprite-sheet, godot, unreal, texture-atlas
.venv/bin/pixelforge plan "a knight with a flaming sword" --mode character   # Scene Graph, no image
.venv/bin/pixelforge palette 8bit-console                 # analysis; also --compress N, --simulate deuteranopia
.venv/bin/pixelforge qa sprite.png --repair -o fixed.png  # detect defects; --repair applies safe fixes
.venv/bin/pixelforge character create "Elias" --subject "Captain Elias, veteran knight"  # then: add-frame, drift, list
.venv/bin/pixelforge animate "a knight" --action walk --seed 7 -o /tmp/anim  # seed-anchored, palette-locked frames + GIF + sheet
.venv/bin/pixelforge dataset build /path/to/sprites -o /tmp/ds  # validate/dedup/caption a folder → manifest.jsonl + lora_config.json
.venv/bin/pixelforge project save game.pforge --sprites /tmp/sprites --name "My Game"  # portable workspace archive; also: project load/info
.venv/bin/pixelforge generate "winter armor" --character <id>   # generate AS a stored character
.venv/bin/pixelforge list modes          # also: styles, palettes, export-formats, backends, planning-backends, plugins, actions
.venv/bin/pixelforge benchmark --backend mock   # time + QA-score a fixed suite (speed/quality/VRAM)
.venv/bin/pixelforge system              # device / backend availability
```

CLI source: `backend/src/pixelforge/cli.py`. The `generate` JSON includes the
absolute `path`, `seed`, and `palette_hex` of every image; same seed ⇒ identical
image (deterministic).

## Run the app

```bash
cd backend && .venv/bin/uvicorn pixelforge.main:app --port 8765   # API on :8765
cd frontend && npm run dev                                        # Electron + Vite
# UI only (e.g. headless VM): npx vite → http://localhost:5173
```

Key API endpoints (all JSON): `POST /api/generate`, `GET /api/jobs/{id}`,
`WS /api/ws/jobs/{id}` (progress), `GET /api/images/{filename}`,
`GET /api/modes|styles|palettes`, `POST /api/export`, `GET /api/system`.

## Verify changes (run before committing)

```bash
cd backend && .venv/bin/ruff check src tests && .venv/bin/ruff format --check src tests \
    && .venv/bin/mypy src && .venv/bin/pytest -q
cd frontend && npm run check     # eslint + tsc + vitest
```

## Code map

- `backend/src/pixelforge/generation/pipeline.py` — 4-stage pipeline (diffusion → pixelize → palette → cleanup)
- `backend/src/pixelforge/generation/tileize.py` — seamless tiling (M22): pure wrap-aware seam-blend `make_tileable` + `seam_metrics`/`seam_score`; applied before quantization when `request.tileable`. Seam QA in `qa/detectors/seam.py`; 47-tile `wang-blob` exporter in `exporters/wang_blob.py` (shared `build_blob_sheet`). Engine tilesets (M24): `exporters/godot_tileset.py` (`godot-tileset` → Godot 4 `.tres` with terrain peering bits) + `exporters/tiled_tileset.py` (`tiled-tileset` → `.tsx` wangset + sample `.tmx`), both from the blob masks. `pixelforge generate --tileable`, `pixelforge export --format wang-blob|godot-tileset|tiled-tileset`
- `backend/src/pixelforge/generation/backends/` — `mock.py`, `flux.py` (M2: fp8/offload/ControlNet, decisions in torch-free `flux_config.py`); register new models in `registry.py`
- `backend/src/pixelforge/generation/benchmark.py` — benchmark suite (M2): times + QA-scores generations; `pixelforge benchmark`. Golden-image regression in `backend/tests/golden/` (`PIXELFORGE_UPDATE_GOLDEN=1` to refresh)
- `backend/src/pixelforge/core/scene_graph.py` — the `SceneGraph` (D-009): structured, typed plan for one generation
- `backend/src/pixelforge/agents/` — agentic planning layer (D-010): seven agents (`intent`, `art-director`, `composition`, `silhouette`, `lighting`, `material`, `animation`), `PlanningRuntime`, swappable `planning_backends/` (deterministic `mock`); off by default (`planning_enabled`), compiled by `generation/plan_compiler.py` (incl. silhouette control map + provenance sidecar)
- `backend/src/pixelforge/qa/` — Pixel QA engine (D-013): deterministic `detectors/` + safe repairs, `HeuristicCritic`, `QAEngine`; Layer 2 `repair_loop.py` (QA-gated region-repair loop, swappable `RegionRegenerator`); semantic `VLMCritic` over swappable `critic_backends/` (mock + gated VLM); off by default (`qa_enabled`, `qa_repair_loop`, `qa_critic`), exposed via `POST /api/qa` and `pixelforge qa [--repair-loop] [--critic vlm --subject ...]`
- `backend/src/pixelforge/memory/` — character memory (D-011): `Character` store + reference frames + identity embeddings (mock backend), drift gate; opt-in per request via `character_id`, exposed via `/api/characters` and `pixelforge character`
- `backend/src/pixelforge/palettes/`, `styles/`, `modes/`, `exporters/` — data-driven registries; extend by adding entries, not by editing consumers
- `backend/src/pixelforge/animation/` — animation (D-009, M18/M19): `actions.py` (13 templates), `sequence.py` (`AnimationSequence`: seed-anchored + palette-locked frames, per-frame QA, reference chaining + per-frame identity-consistency reusing D-011 embeddings), `assembly.py` (GIF + sprite sheet); `POST /api/animation/generate`, `pixelforge animate [--reference-chain --consistency]`
- `backend/src/pixelforge/tileset/` — Tileset generation (D-001, M23): `service.py` (`TileSet`: base tile + N seam-locked variants sharing one seed + one locked palette; edge-locked via `tileize.lock_edges_to` + re-quantize, checked with `edge_consistency`; variants assembled into the 47-tile Wang/blob sheet); `POST /api/tileset/generate`, `pixelforge tileset "<prompt>" --variants N`, Tileset tab
- `backend/src/pixelforge/dataset/` — Dataset & LoRA-training toolkit (D-001, M21): `builder.py` (pure `build_dataset`: validate → dedup → caption → kohya `manifest.jsonl` + `lora_config.json`), `phash.py` (NEAREST-resize dHash + Hamming clustering, cross-machine deterministic), `caption.py` (reuses D-012 palette signals, no model), `trainer.py` (`LoraTrainer` gated like FLUX); `POST /api/dataset`, `pixelforge dataset build <dir>`, Dataset tab
- `backend/src/pixelforge/plugins/` — Plugin SDK (D-014): `loader.py` discovers `pixelforge.*` entry points + required `PluginManifest`, registers into existing registries; off by default (`plugins_enabled` + `plugin_allowlist`), exposed via `GET /api/plugins` and `pixelforge list plugins`. Guide: `docs/developer/plugins.md`; sample: `examples/plugins/pixelforge-hello`
- `backend/src/pixelforge/projects/bundle.py` — portable `.pforge` project bundles (D-001, M25): deterministic `ZIP_STORED` archive (manifest.json + PNGs, byte-stable `save→load→save`), atomic writes, schema `migrate_manifest` hook, `AutosaveManager` recovery; `POST /api/project/save|load`, `pixelforge project save|load|info`, header Project bar
- `backend/src/pixelforge/config/settings.py` — all backend configuration (env-overridable, `PIXELFORGE_` prefix)
- `frontend/src/renderer/` — React UI; `state/editorStore.ts` (Zustand, immutable undo snapshots), `features/editor/pixelOps.ts` (pure pixel ops)
- `frontend/src/renderer/features/{plan,qa,characters,palettes,dataset}/` — UI for the agentic layer (M13) + Dataset tab (M21): plan preview, QA panel, character manager, palette lab, dataset builder; pure view helpers (`planView.ts`, `qaView.ts`, `datasetView.ts`) are unit-tested, React components are not (test env is node-only)
- `frontend/src/renderer/features/generation/{TilePreview.tsx,tileView.ts}` — seamless-tiling toggle + live 3×3 tiling preview with a seamlessness readout (M22); pure `tileView.ts` (`seamScore`) is unit-tested
- `frontend/src/renderer/features/tileset/` — Tileset tab (M23): generate a seam-locked terrain family, pick a variant brush, paint an N×N grid that renders tiles edge-to-edge, coherence badge + 47-tile blob sheet; pure `tilesetView.ts` unit-tested
- `frontend/src/shared/config.ts` — frontend configuration

## Conventions

- Registries over conditionals: new modes/styles/palettes/exporters/backends plug into existing registries.
- Backend: typed Python, pydantic models, no `Any`; ruff + mypy must pass.
- Frontend: strict TypeScript; pixel operations are pure functions, state changes go through the Zustand store.
- Tests live in `backend/tests/` and next to frontend sources (`*.test.ts`).
- Generated artifacts (weights, outputs, `~/.pixelforge`) are never committed.
