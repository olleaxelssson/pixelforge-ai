# PixelForge AI

An AI-native pixel art generation platform: a cross-platform desktop application that generates
professional, game-ready pixel art from text prompts, reference images, and sketches — with an
integrated pixel editor, palette system, animation tools, and engine-ready exporters.

**Not** an image downscaler. PixelForge runs a diffusion model tuned for pixel art and then applies
a dedicated pixel-refinement stage (grid snapping, palette quantization, outline cleanup) so output
has crisp pixels, limited palettes, and readable silhouettes.

## Highlights

- **Local-only inference** — fully offline. GPU (CUDA / Apple Silicon MPS) with CPU fallback.
- **Commercial-safe models** — FLUX.1-schnell (Apache-2.0) primary backend; every bundled model
  and dependency is Apache/MIT-compatible. See [docs/research/model-research.md](docs/research/model-research.md).
- **15 generation modes** — text/image/sketch to pixel art, characters, creatures, environments,
  items, weapons, armor, portraits, icons, tilesets, backgrounds, UI elements, sprite sheets.
- **Native sizes** — 16×16 up to 256×256 and custom resolutions, generated at target pixel grid.
- **Animation** — idle/walk/run/attack/death/hurt/jump/cast/mining/fishing/woodcutting/crafting/farming,
  sprite sheets and animated GIF previews.
- **Palette system** — locking, extraction, optimization, swapping, import/export, retro-console-inspired presets.
- **Integrated pixel editor** — pencil, eraser, fill, shapes, selection, layers, onion skinning, animation timeline.
- **Exports** — PNG, GIF, sprite sheets, texture atlases, Unity / Godot / Unreal-ready assets.

## Repository Layout

| Path | Purpose |
|---|---|
| `backend/` | Python FastAPI backend: generation pipeline, palettes, exporters, job queue |
| `frontend/` | Electron + React + TypeScript desktop app |
| `docs/` | Architecture, research, user guide, troubleshooting |
| `scripts/` | Setup and development scripts |
| `examples/` | Example palettes and prompts |

Configuration is centralized in `backend/src/pixelforge/config/settings.py` (env-overridable via
`PIXELFORGE_*` variables) and `frontend/src/shared/config.ts`.

Key documents: [ARCHITECTURE.md](ARCHITECTURE.md) · [DECISIONS.md](DECISIONS.md) ·
[ROADMAP.md](ROADMAP.md) · [CONTRIBUTING.md](CONTRIBUTING.md)

## Quick Start

```bash
# One-shot setup (Linux/macOS)
./scripts/setup.sh

# Backend (dev)
cd backend && python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"          # add ".[ml]" for real model inference
uvicorn pixelforge.main:app --reload --port 8765

# Frontend (dev)
cd frontend && npm install && npm run dev
```

Without the `[ml]` extra installed, the backend runs with a deterministic **mock generation
backend** — useful for UI development and CI. Install `[ml]` (PyTorch + diffusers) for real
generation; FLUX.1-schnell weights download automatically on first use.

## Development Status

Phase 1 (foundation): backend generation pipeline, palette/style/mode systems, exporters,
job queue and API, Electron/React shell with generation UI and pixel editor, tests, and CI.
See [ROADMAP.md](ROADMAP.md) for what's next (real-model quality pass, animation orchestration,
training/dataset tools, editor depth, packaging).

## License

MIT — see [LICENSE](LICENSE). Model weights are governed by their own licenses (FLUX.1-schnell: Apache-2.0).
