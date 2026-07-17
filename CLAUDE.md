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
.venv/bin/pixelforge export /tmp/sprites/cli_0.png --format unity --scale 4 -o /tmp/export
.venv/bin/pixelforge plan "a knight with a flaming sword" --mode character   # Scene Graph, no image
.venv/bin/pixelforge palette 8bit-console                 # analysis; also --compress N, --simulate deuteranopia
.venv/bin/pixelforge qa sprite.png --repair -o fixed.png  # detect defects; --repair applies safe fixes
.venv/bin/pixelforge character create "Elias" --subject "Captain Elias, veteran knight"  # then: add-frame, drift, list
.venv/bin/pixelforge generate "winter armor" --character <id>   # generate AS a stored character
.venv/bin/pixelforge list modes          # also: styles, palettes, export-formats, backends, planning-backends
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
- `backend/src/pixelforge/generation/backends/` — `mock.py`, `flux.py`; register new models in `registry.py`
- `backend/src/pixelforge/core/scene_graph.py` — the `SceneGraph` (D-009): structured, typed plan for one generation
- `backend/src/pixelforge/agents/` — agentic planning layer (D-010): seven agents (`intent`, `art-director`, `composition`, `silhouette`, `lighting`, `material`, `animation`), `PlanningRuntime`, swappable `planning_backends/` (deterministic `mock`); off by default (`planning_enabled`), compiled by `generation/plan_compiler.py` (incl. silhouette control map + provenance sidecar)
- `backend/src/pixelforge/qa/` — Pixel QA engine (D-013): deterministic `detectors/` + safe repairs, `HeuristicCritic`, `QAEngine`; off by default (`qa_enabled`), exposed via `POST /api/qa` and `pixelforge qa`
- `backend/src/pixelforge/memory/` — character memory (D-011): `Character` store + reference frames + identity embeddings (mock backend), drift gate; opt-in per request via `character_id`, exposed via `/api/characters` and `pixelforge character`
- `backend/src/pixelforge/palettes/`, `styles/`, `modes/`, `exporters/`, `animation/` — data-driven registries; extend by adding entries, not by editing consumers
- `backend/src/pixelforge/config/settings.py` — all backend configuration (env-overridable, `PIXELFORGE_` prefix)
- `frontend/src/renderer/` — React UI; `state/editorStore.ts` (Zustand, immutable undo snapshots), `features/editor/pixelOps.ts` (pure pixel ops)
- `frontend/src/shared/config.ts` — frontend configuration

## Conventions

- Registries over conditionals: new modes/styles/palettes/exporters/backends plug into existing registries.
- Backend: typed Python, pydantic models, no `Any`; ruff + mypy must pass.
- Frontend: strict TypeScript; pixel operations are pure functions, state changes go through the Zustand store.
- Tests live in `backend/tests/` and next to frontend sources (`*.test.ts`).
- Generated artifacts (weights, outputs, `~/.pixelforge`) are never committed.
