"""Application service container, assembled at startup (dependency injection)."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from fastapi import Request

from pixelforge.config import Settings, get_settings
from pixelforge.core.errors import JobCancelledError
from pixelforge.core.models import GenerationResult, Job
from pixelforge.core.queue import JobQueue
from pixelforge.generation.pipeline import GenerationPipeline
from pixelforge.modes.registry import ModeRegistry
from pixelforge.palettes.service import PaletteService
from pixelforge.projects.store import ProjectStore
from pixelforge.styles.registry import StyleRegistry


@dataclass
class AppState:
    settings: Settings
    queue: JobQueue
    pipeline: GenerationPipeline
    modes: ModeRegistry
    styles: StyleRegistry
    palettes: PaletteService
    projects: ProjectStore


def build_app_state() -> AppState:
    settings = get_settings()
    modes = ModeRegistry()
    styles = StyleRegistry(user_dir=settings.user_styles_dir)
    palettes = PaletteService(user_dir=settings.user_palettes_dir)
    projects = ProjectStore(projects_dir=settings.projects_dir)
    pipeline = GenerationPipeline(
        backend_name=settings.backend,
        outputs_dir=settings.outputs_dir,
        modes=modes,
        styles=styles,
        palettes=palettes,
        diffusion_resolution=settings.diffusion_resolution,
        diffusion_steps=settings.diffusion_steps,
    )

    async def run_job(job: Job, queue: JobQueue) -> GenerationResult:
        loop = asyncio.get_running_loop()

        def on_progress(stage: str, percent: float) -> None:
            # Runs in the worker thread: raising here aborts the pipeline promptly.
            if queue.is_cancelled(job.id):
                raise JobCancelledError(job.id)
            loop.call_soon_threadsafe(queue.report_progress, job, stage, percent)

        return await asyncio.to_thread(pipeline.run, job.id, job.request, on_progress)

    queue = JobQueue(runner=run_job, max_size=settings.max_queue_size)
    return AppState(
        settings=settings,
        queue=queue,
        pipeline=pipeline,
        modes=modes,
        styles=styles,
        palettes=palettes,
        projects=projects,
    )


def get_state(request: Request) -> AppState:
    return request.app.state.services
