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
