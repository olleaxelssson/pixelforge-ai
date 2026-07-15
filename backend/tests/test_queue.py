import asyncio

import pytest

from pixelforge.core.models import GenerationRequest, GenerationResult, JobStatus
from pixelforge.core.queue import JobQueue


@pytest.mark.asyncio
async def test_queue_completes_job():
    async def runner(job, queue):
        queue.report_progress(job, "work", 50.0)
        return GenerationResult()

    queue = JobQueue(runner=runner)
    queue.start()
    job = await queue.submit(GenerationRequest(prompt="x"))
    for _ in range(100):
        if queue.get(job.id).status is JobStatus.COMPLETED:
            break
        await asyncio.sleep(0.01)
    assert queue.get(job.id).status is JobStatus.COMPLETED
    assert queue.get(job.id).progress.percent == 100.0
    await queue.stop()


@pytest.mark.asyncio
async def test_queue_failure_does_not_kill_worker():
    calls = []

    async def runner(job, queue):
        calls.append(job.id)
        if len(calls) == 1:
            raise RuntimeError("boom")
        return GenerationResult()

    queue = JobQueue(runner=runner)
    queue.start()
    first = await queue.submit(GenerationRequest(prompt="a"))
    second = await queue.submit(GenerationRequest(prompt="b"))
    for _ in range(100):
        if queue.get(second.id).status is JobStatus.COMPLETED:
            break
        await asyncio.sleep(0.01)
    assert queue.get(first.id).status is JobStatus.FAILED
    assert queue.get(first.id).error == "boom"
    assert queue.get(second.id).status is JobStatus.COMPLETED
    await queue.stop()


@pytest.mark.asyncio
async def test_cancel_queued_job():
    started = asyncio.Event()
    release = asyncio.Event()

    async def runner(job, queue):
        started.set()
        await release.wait()
        return GenerationResult()

    queue = JobQueue(runner=runner)
    queue.start()
    running = await queue.submit(GenerationRequest(prompt="run"))
    waiting = await queue.submit(GenerationRequest(prompt="wait"))
    await started.wait()
    assert queue.cancel(waiting.id)
    assert queue.get(waiting.id).status is JobStatus.CANCELLED
    release.set()
    for _ in range(100):
        if queue.get(running.id).status is JobStatus.COMPLETED:
            break
        await asyncio.sleep(0.01)
    assert queue.get(running.id).status is JobStatus.COMPLETED
    await queue.stop()


@pytest.mark.asyncio
async def test_subscribe_receives_updates():
    async def runner(job, queue):
        queue.report_progress(job, "half", 50.0)
        return GenerationResult()

    queue = JobQueue(runner=runner)
    job = await queue.submit(GenerationRequest(prompt="x"))
    updates = queue.subscribe(job.id)
    queue.start()
    seen = []
    for _ in range(10):
        update = await asyncio.wait_for(updates.get(), timeout=2.0)
        seen.append(update.status)
        if update.status is JobStatus.COMPLETED:
            break
    assert JobStatus.COMPLETED in seen
    await queue.stop()
