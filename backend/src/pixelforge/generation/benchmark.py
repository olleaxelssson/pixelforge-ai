"""Generation benchmark harness (M2, D-002): measure quality, don't assert it.

Runs a fixed prompt suite through whatever backend is active, times each generation, and scores the
output with the QA engine (D-013) — so quality is a *number* that can be tracked across changes and
compared between the mock and a real FLUX backend. Works fully in CI against the deterministic mock;
the same harness reports real wall-time and VRAM on a GPU box.
"""

from __future__ import annotations

from pathlib import Path
from time import perf_counter

from PIL import Image
from pydantic import BaseModel, Field

from pixelforge.core.models import GenerationRequest
from pixelforge.generation.pipeline import GenerationPipeline
from pixelforge.qa.engine import QAEngine
from pixelforge.qa.models import DetectorContext, QAScores


class BenchmarkCase(BaseModel):
    prompt: str
    mode: str = "text-to-pixel"
    size: int = 32
    seed: int = 0
    palette_id: str | None = None
    max_colors: int = 16


class BenchmarkResult(BaseModel):
    prompt: str
    seed: int
    wall_ms: float
    passed: bool
    scores: QAScores


class BenchmarkAggregate(BaseModel):
    cases: int
    mean_wall_ms: float
    mean_overall: float
    pass_rate: float


class BenchmarkReport(BaseModel):
    backend: str
    device: str
    peak_vram_mb: float | None = None
    results: list[BenchmarkResult] = Field(default_factory=list)
    aggregate: BenchmarkAggregate


def default_suite() -> list[BenchmarkCase]:
    """A small, representative spread of subjects/sizes for quick regression tracking."""
    return [
        BenchmarkCase(prompt="a knight with a flaming sword", mode="character", size=32, seed=1),
        BenchmarkCase(prompt="health potion", mode="item", size=32, seed=2),
        BenchmarkCase(prompt="a mossy dungeon tile", mode="tileset", size=32, seed=3),
        BenchmarkCase(prompt="a slime monster", mode="character", size=16, seed=4),
        BenchmarkCase(prompt="a treasure chest", mode="item", size=48, seed=5),
    ]


def run_benchmark(
    pipeline: GenerationPipeline,
    cases: list[BenchmarkCase],
    outputs_dir: Path,
    qa_engine: QAEngine | None = None,
    backend: str = "mock",
    device: str = "cpu",
    peak_vram_mb: float | None = None,
) -> BenchmarkReport:
    engine = qa_engine or QAEngine()
    results: list[BenchmarkResult] = []

    for index, case in enumerate(cases):
        request = GenerationRequest(
            prompt=case.prompt,
            mode=case.mode,
            width=case.size,
            height=case.size,
            seed=case.seed,
            batch_size=1,
            palette_id=case.palette_id,
            max_colors=case.max_colors,
        )
        start = perf_counter()
        result = pipeline.run(f"bench_{index}", request, lambda _stage, _percent: None)
        wall_ms = (perf_counter() - start) * 1000.0

        image = Image.open(outputs_dir / result.images[0].filename)
        report = engine.run(
            image, DetectorContext(max_colors=case.max_colors, transparent_background=True)
        )
        results.append(
            BenchmarkResult(
                prompt=case.prompt,
                seed=case.seed,
                wall_ms=round(wall_ms, 2),
                passed=report.passed,
                scores=report.scores,
            )
        )

    n = len(results) or 1
    aggregate = BenchmarkAggregate(
        cases=len(results),
        mean_wall_ms=round(sum(r.wall_ms for r in results) / n, 2),
        mean_overall=round(sum(r.scores.overall for r in results) / n, 3),
        pass_rate=round(sum(1 for r in results if r.passed) / n, 3),
    )
    return BenchmarkReport(
        backend=backend,
        device=device,
        peak_vram_mb=peak_vram_mb,
        results=results,
        aggregate=aggregate,
    )
