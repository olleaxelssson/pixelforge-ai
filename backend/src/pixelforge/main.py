"""FastAPI application entrypoint.

Run with: ``uvicorn pixelforge.main:app --port 8765``
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from pixelforge import __version__
from pixelforge.api.routers import (
    animation,
    catalog,
    characters,
    dataset,
    export,
    generation,
    palettes,
    plan,
    plugins,
    projects,
    qa,
    tileset,
)
from pixelforge.api.state import build_app_state
from pixelforge.core.logging_setup import configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    app.state.services = build_app_state()
    app.state.services.queue.start()
    yield
    await app.state.services.queue.stop()


app = FastAPI(title="PixelForge AI", version=__version__, lifespan=lifespan)

# Local desktop app: renderer runs on a dev-server or file:// origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],  # so the renderer can read the export filename
)

app.include_router(generation.router)
app.include_router(catalog.router)
app.include_router(palettes.router)
app.include_router(export.router)
app.include_router(projects.router)
app.include_router(plan.router)
app.include_router(qa.router)
app.include_router(characters.router)
app.include_router(animation.router)
app.include_router(plugins.router)
app.include_router(dataset.router)
app.include_router(tileset.router)


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


def run() -> None:
    import uvicorn

    from pixelforge.config import get_settings

    settings = get_settings()
    uvicorn.run(app, host=settings.host, port=settings.port)


if __name__ == "__main__":
    run()
