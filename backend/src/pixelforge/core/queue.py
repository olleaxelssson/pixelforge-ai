"""Async in-process job queue with cancellation and progress events.

A single worker task processes generation jobs sequentially (one model run at a
time). Progress updates are fanned out to subscribers via per-job asyncio queues,
which the WebSocket layer consumes.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Awaitable, Callable

from pixelforge.core.errors import JobCancelledError
from pixelforge.core.models import GenerationRequest, GenerationResult, Job, JobStatus

logger = logging.getLogger("pixelforge.queue")

JobRunner = Callable[[Job, "JobQueue"], Awaitable[GenerationResult]]


class JobQueue:
    def __init__(self, runner: JobRunner, max_size: int = 64) -> None:
        self._runner = runner
        self._pending: asyncio.Queue[str] = asyncio.Queue(maxsize=max_size)
        self._jobs: dict[str, Job] = {}
        self._cancelled: set[str] = set()
        self._subscribers: dict[str, list[asyncio.Queue[Job]]] = {}
        self._worker: asyncio.Task[None] | None = None

    def start(self) -> None:
        if self._worker is None:
            self._worker = asyncio.create_task(self._work_loop())

    async def stop(self) -> None:
        if self._worker is not None:
            self._worker.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._worker
            self._worker = None

    async def submit(self, request: GenerationRequest) -> Job:
        job = Job(request=request)
        self._jobs[job.id] = job
        await self._pending.put(job.id)
        return job

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def list_jobs(self) -> list[Job]:
        return list(self._jobs.values())

    def cancel(self, job_id: str) -> bool:
        job = self._jobs.get(job_id)
        if job is None or job.status in (
            JobStatus.COMPLETED,
            JobStatus.FAILED,
            JobStatus.CANCELLED,
        ):
            return False
        self._cancelled.add(job_id)
        if job.status is JobStatus.QUEUED:
            self._finish(job, JobStatus.CANCELLED)
        return True

    def is_cancelled(self, job_id: str) -> bool:
        return job_id in self._cancelled

    def report_progress(self, job: Job, stage: str, percent: float) -> None:
        job.progress.stage = stage
        job.progress.percent = round(percent, 1)
        self._notify(job)

    def subscribe(self, job_id: str) -> asyncio.Queue[Job]:
        queue: asyncio.Queue[Job] = asyncio.Queue()
        self._subscribers.setdefault(job_id, []).append(queue)
        return queue

    def unsubscribe(self, job_id: str, queue: asyncio.Queue[Job]) -> None:
        subscribers = self._subscribers.get(job_id, [])
        if queue in subscribers:
            subscribers.remove(queue)

    async def _work_loop(self) -> None:
        while True:
            job_id = await self._pending.get()
            job = self._jobs[job_id]
            if job.status is not JobStatus.QUEUED:
                continue
            job.status = JobStatus.RUNNING
            self._notify(job)
            try:
                result = await self._runner(job, self)
                job.result = result
                self._finish(job, JobStatus.COMPLETED)
            except JobCancelledError:
                self._finish(job, JobStatus.CANCELLED)
            except Exception as exc:  # noqa: BLE001 - job failures must not kill the worker
                logger.exception("job %s failed", job.id)
                job.error = str(exc)
                self._finish(job, JobStatus.FAILED)

    def _finish(self, job: Job, status: JobStatus) -> None:
        job.status = status
        if status is JobStatus.COMPLETED:
            job.progress.stage = "done"
            job.progress.percent = 100.0
        self._notify(job)

    def _notify(self, job: Job) -> None:
        for queue in self._subscribers.get(job.id, []):
            queue.put_nowait(job.model_copy(deep=True))
