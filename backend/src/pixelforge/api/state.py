"""Application service container, assembled at startup (dependency injection)."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from fastapi import Request

from pixelforge.agents.planning_backends.registry import get_planning_backend
from pixelforge.agents.runtime import PlanningRuntime
from pixelforge.animation.sequence import AnimationSequence
from pixelforge.config import Settings, get_settings
from pixelforge.core.errors import JobCancelledError
from pixelforge.core.models import GenerationResult, Job
from pixelforge.core.queue import JobQueue
from pixelforge.generation.pipeline import GenerationPipeline
from pixelforge.memory.embeddings import get_embedding_backend
from pixelforge.memory.service import CharacterMemory
from pixelforge.memory.store import CharacterStore
from pixelforge.modes.registry import ModeRegistry
from pixelforge.palettes.service import PaletteService
from pixelforge.plugins.loader import load_plugins
from pixelforge.plugins.manifest import PluginReport
from pixelforge.projects.store import ProjectStore
from pixelforge.qa.critic import HeuristicCritic, VLMCritic
from pixelforge.qa.critic_backends.registry import get_critic_backend
from pixelforge.qa.engine import QAEngine
from pixelforge.qa.repair_loop import RepairLoop
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
    planner: PlanningRuntime | None
    qa: QAEngine
    characters: CharacterMemory
    animation: AnimationSequence
    plugins: PluginReport


def build_app_state() -> AppState:
    settings = get_settings()
    # Plugins register into the registries below, so they load before anything consumes them.
    plugins = load_plugins(settings)
    modes = ModeRegistry()
    styles = StyleRegistry(user_dir=settings.user_styles_dir)
    palettes = PaletteService(user_dir=settings.user_palettes_dir)
    projects = ProjectStore(projects_dir=settings.projects_dir)
    planner = (
        PlanningRuntime(
            backend=get_planning_backend(settings.planning_backend), modes=modes, styles=styles
        )
        if settings.planning_enabled
        else None
    )
    critic = (
        VLMCritic(get_critic_backend(settings.vlm_critic_backend))
        if settings.qa_critic == "vlm"
        else HeuristicCritic()
    )
    qa = QAEngine(critic=critic, pass_threshold=settings.qa_pass_threshold)
    repair_loop = (
        RepairLoop(engine=qa, max_iterations=settings.qa_repair_max_iterations)
        if (settings.qa_enabled and settings.qa_repair_loop)
        else None
    )
    characters = CharacterMemory(
        store=CharacterStore(characters_dir=settings.characters_dir),
        embeddings=get_embedding_backend(settings.memory_embedding_backend),
        drift_threshold=settings.memory_drift_threshold,
    )
    pipeline = GenerationPipeline(
        backend_name=settings.backend,
        outputs_dir=settings.outputs_dir,
        modes=modes,
        styles=styles,
        palettes=palettes,
        diffusion_resolution=settings.diffusion_resolution,
        diffusion_steps=settings.diffusion_steps,
        planner=planner,
        qa_engine=qa if (settings.qa_enabled and settings.qa_autorepair) else None,
        repair_loop=repair_loop,
    )
    animation = AnimationSequence(
        pipeline=pipeline,
        outputs_dir=settings.outputs_dir,
        qa_engine=qa if settings.qa_enabled else None,
        embeddings=get_embedding_backend(settings.memory_embedding_backend),
        drift_threshold=settings.memory_drift_threshold,
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
        planner=planner,
        qa=qa,
        characters=characters,
        animation=animation,
        plugins=plugins,
    )


def get_state(request: Request) -> AppState:
    return request.app.state.services
