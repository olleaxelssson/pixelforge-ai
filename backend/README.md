# PixelForge Backend

Python FastAPI backend: generation pipeline, palettes, exporters, job queue.
See the repository root [README](../README.md) and [ARCHITECTURE.md](../ARCHITECTURE.md).

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"     # add ".[ml]" for real model inference
uvicorn pixelforge.main:app --reload --port 8765
make check                  # lint + typecheck + tests
```
