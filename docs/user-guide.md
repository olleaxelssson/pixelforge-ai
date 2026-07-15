# PixelForge AI — User Guide

## Starting the app

```bash
./scripts/setup.sh          # one-time setup
cd backend && .venv/bin/uvicorn pixelforge.main:app --port 8765   # terminal 1
cd frontend && npm run dev                                        # terminal 2
```

The header shows backend status and the active compute device (`cuda`, `mps`, or `cpu`).

Without ML extras installed, generation uses the deterministic **mock backend**
(procedural sprites) — useful for exploring the full workflow offline. Install
real inference with `PIXELFORGE_INSTALL_ML=1 ./scripts/setup.sh`; FLUX.1-schnell
weights (~24 GB) download on first generation.

## Generating pixel art

1. Pick a **mode** (character, item, tileset, …). Modes set sensible default
   sizes and transparency.
2. Write a **prompt**. Style presets add pixel-art-specific prompt scaffolding,
   so describe the subject, not the medium.
3. Choose a **size** (16×16–256×256). Art is generated at high resolution and
   pixelized to the exact target grid — every output is true pixel art.
4. Optionally lock a **palette**; otherwise an optimized palette is extracted
   (bounded by *max colors*).
5. Set **seed** for reproducibility, **batch** for variations, then Generate.

Progress streams live (diffusion → pixelize → palette → cleanup). Jobs can be
cancelled from the queue.

## Editing

Click any result to open it in the integrated editor:

- Tools: pencil, eraser, fill, line, rectangle (Shift = filled), ellipse, move
- Layers: add, hide, select
- Undo/redo: Ctrl+Z / Ctrl+Y
- Zoom: Ctrl+scroll; grid toggle in the toolbar

## Exporting

Use `POST /api/export` (UI export dialog planned — see ROADMAP.md) with formats:
`png`, `gif`, `spritesheet`, `atlas`, `unity`, `godot`, `unreal`.

## Palettes

`GET/POST /api/palettes` manages palettes; JSON, JASC-PAL (`.pal`) and
GIMP (`.gpl`) files are supported. Built-in presets are inspired by classic
hardware color constraints (no copyrighted assets).
