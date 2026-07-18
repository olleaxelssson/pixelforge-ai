"""Benchmark harness tests (M2, D-002): runs the suite through the mock pipeline."""

from __future__ import annotations

import json
from pathlib import Path

from pixelforge.generation.benchmark import (
    BenchmarkCase,
    default_suite,
    run_benchmark,
)
from pixelforge.generation.pipeline import GenerationPipeline
from pixelforge.modes.registry import ModeRegistry
from pixelforge.palettes.service import PaletteService
from pixelforge.styles.registry import StyleRegistry


def _pipeline(outputs_dir: Path) -> GenerationPipeline:
    return GenerationPipeline(
        backend_name="mock",
        outputs_dir=outputs_dir,
        modes=ModeRegistry(),
        styles=StyleRegistry(),
        palettes=PaletteService(user_dir=outputs_dir / "palettes"),
    )


def test_run_benchmark_scores_every_case(tmp_path) -> None:
    cases = [
        BenchmarkCase(prompt="a knight", mode="character", size=24, seed=1),
        BenchmarkCase(prompt="a potion", mode="item", size=24, seed=2),
    ]
    report = run_benchmark(_pipeline(tmp_path), cases, tmp_path)

    assert report.aggregate.cases == 2
    assert len(report.results) == 2
    assert 0.0 <= report.aggregate.mean_overall <= 1.0
    assert 0.0 <= report.aggregate.pass_rate <= 1.0
    assert report.peak_vram_mb is None  # no CUDA in CI
    for result in report.results:
        assert result.wall_ms >= 0.0
        assert 0.0 <= result.scores.overall <= 1.0


def test_default_suite_runs(tmp_path) -> None:
    report = run_benchmark(_pipeline(tmp_path), default_suite(), tmp_path)
    assert report.aggregate.cases == len(default_suite())
    # Report round-trips through JSON (CLI + API surface).
    assert json.loads(report.model_dump_json())["aggregate"]["cases"] == len(default_suite())


def test_cli_benchmark(monkeypatch, tmp_path, capsys) -> None:
    from pixelforge.cli import main

    monkeypatch.setenv("PIXELFORGE_BACKEND", "mock")
    from pixelforge.config import get_settings

    get_settings.cache_clear()
    assert main(["benchmark", "--backend", "mock"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["backend"] == "mock"
    assert payload["aggregate"]["cases"] == len(default_suite())
    get_settings.cache_clear()
