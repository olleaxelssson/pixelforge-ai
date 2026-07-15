# Troubleshooting

## Backend shows "offline" in the app header
- Ensure the backend is running: `cd backend && .venv/bin/uvicorn pixelforge.main:app --port 8765`
- Check the port: frontend expects `127.0.0.1:8765` (see `frontend/src/shared/config.ts`,
  backend `PIXELFORGE_PORT`).

## Generation produces procedural blobs instead of real art
The mock backend is active. Install ML extras (`pip install -e ".[ml]"` in
`backend/`) and restart. Check `GET /api/system` to see which backends are available.

## CUDA not used despite having an NVIDIA GPU
- Verify `python -c "import torch; print(torch.cuda.is_available())"`.
- Install a CUDA-enabled torch build: https://pytorch.org/get-started/locally/
- Force a device with `PIXELFORGE_DEVICE=cuda`.

## Out-of-memory during generation
- FLUX.1-schnell needs ~12 GB VRAM with CPU offload enabled (default on CUDA).
- Reduce `PIXELFORGE_DIFFUSION_RESOLUTION` (e.g. 768 or 512).
- CPU inference works but is slow (minutes per image).

## First generation is very slow
Model weights (~24 GB) download from Hugging Face on first use and are cached
under `~/.cache/huggingface`. Subsequent runs load from cache.

## `pip install -e ".[dev]"` fails
- Requires Python ≥ 3.10 (`python3 --version`).
- Upgrade pip first: `.venv/bin/pip install --upgrade pip`.

## Where is my data?
Generated images, projects, and user palettes live under `~/.pixelforge/`
(override with `PIXELFORGE_DATA_DIR`).
