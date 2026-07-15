# Contributing to PixelForge AI

This project is developed collaboratively by humans and AI coding assistants (Devin, Claude Code).
These conventions keep it easy for any agent to understand and extend.

## Project Conventions

### General
- Read `ARCHITECTURE.md` before changing subsystem boundaries; record significant decisions in `DECISIONS.md`.
- Prefer many small, focused modules over large files. One concept per file.
- Descriptive names everywhere; no abbreviations that require context to decode.
- Comments only where logic is genuinely non-obvious. No commented-out code.
- All configuration goes through the central config modules — never scatter constants.

### Backend (Python 3.10+)
- Source in `backend/src/pixelforge/`; tests in `backend/tests/` mirroring the package layout.
- Style: `ruff` (lint + format), `mypy --strict`-leaning typing. Run `make -C backend check`.
- Pydantic models for all API request/response types; no untyped dicts across module boundaries.
- New generation backends implement `GenerationBackend` and register in `generation/backends/registry.py`.
- New exporters implement `Exporter` and register in `exporters/registry.py`.
- Business logic never lives in API routers.

### Frontend (TypeScript, React, Electron)
- Source in `frontend/src/` (`main/` = Electron main, `renderer/` = React app).
- Style: eslint + prettier; strict TypeScript (`tsc --noEmit` must pass). Run `npm run check`.
- State in Zustand stores under `renderer/state/`; components stay presentational where possible.
- API types in `renderer/api/types.ts` must mirror backend pydantic models — update both together.

### Styles / Modes / Palettes
Data-driven: add TOML (styles, modes) or JSON/GPL/PAL (palettes) files — see `backend/src/pixelforge/styles/presets/` for examples. No code changes required.

## Workflow
1. Branch from `main`; small, reviewable PRs.
2. Before pushing: `make -C backend check` and `cd frontend && npm run check && npm test`.
3. CI must be green. Never weaken lint/type rules to pass; fix the code.
4. Update docs affected by your change (README, ARCHITECTURE, user guide) in the same PR.
5. Never commit model weights, datasets, generated artifacts, or secrets.

## Commit Messages
`<area>: <imperative summary>` — e.g. `palettes: add ordered dithering option`.

## Testing Expectations
- New pipeline stages, palette ops, exporters: unit tests (deterministic, no model weights).
- New API endpoints: FastAPI TestClient integration test.
- Bug fixes: regression test reproducing the bug.
