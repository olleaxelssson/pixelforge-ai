"""Palette-intelligence tests (D-012): analysis, dedup, ramps, CVD, compression, API, CLI."""

from __future__ import annotations

import json

import pytest

from pixelforge.cli import main
from pixelforge.palettes.analysis import (
    analyze_palette,
    compress_palette,
    detect_ramps,
    find_duplicates,
    rank_colors,
    simulate_cvd_palette,
)
from pixelforge.palettes.model import Palette

_GB_RAMP = ["#0f2418", "#2f5e3c", "#79a86a", "#c4dea1"]


def _palette(colors: list[str], pid: str = "t") -> Palette:
    return Palette(id=pid, name="Test", colors=colors)


def test_rank_colors_orders_dark_to_light() -> None:
    ranked = rank_colors(_palette(["#ffffff", "#000000", "#808080"]))
    assert [c.hex for c in ranked] == ["#000000", "#808080", "#ffffff"]
    assert ranked[0].luminance <= ranked[-1].luminance


def test_find_duplicates_flags_near_identical() -> None:
    dups = find_duplicates(_palette(["#ff0000", "#fe0000", "#00ff00"]))
    assert any({d.a, d.b} == {"#ff0000", "#fe0000"} for d in dups)


def test_no_duplicates_for_distinct_palette() -> None:
    assert find_duplicates(_palette(["#000000", "#ff0000", "#00ff00", "#0000ff"])) == []


def test_detect_ramps_groups_shades() -> None:
    ramps = detect_ramps(_palette(_GB_RAMP))
    assert any(len(ramp) >= 3 for ramp in ramps)


def test_analyze_flags_cvd_confusion() -> None:
    analysis = analyze_palette(_palette(["#d02828", "#28a028", "#202020", "#e8e8e8"], "unsafe"))
    deuteranopia = next(r for r in analysis.cvd if r.vision == "deuteranopia")
    assert deuteranopia.confusable_pairs
    assert any(s.code == "cvd-deuteranopia" for s in analysis.suggestions)


def test_analyze_readability_and_counts() -> None:
    analysis = analyze_palette(_palette(["#000000", "#ffffff"]))
    assert analysis.color_count == 2
    assert analysis.contrast.max_contrast_ratio == pytest.approx(21.0)
    assert 0.0 <= analysis.readability_score <= 1.0


def test_compress_reduces_to_target_using_original_colors() -> None:
    palette = _palette(
        ["#000000", "#010101", "#ff0000", "#fe0000", "#00ff00", "#0000ff", "#ffffff", "#fefefe"]
    )
    compressed = compress_palette(palette, 4)
    assert len(compressed.colors) <= 4
    assert set(compressed.colors) <= set(palette.colors)


def test_compress_noop_when_already_small() -> None:
    assert set(compress_palette(_palette(["#000000", "#ffffff"]), 8).colors) == {
        "#000000",
        "#ffffff",
    }


def test_compress_invalid_target_raises() -> None:
    with pytest.raises(ValueError, match="target_colors"):
        compress_palette(_palette(["#000000"]), 0)


def test_simulate_cvd_palette_changes_colors() -> None:
    out = simulate_cvd_palette(_palette(["#d02828", "#28a028"]), "deuteranopia")
    assert len(out.colors) == 2
    assert out.colors != ["#d02828", "#28a028"]


# --- API --------------------------------------------------------------------


def test_analyze_endpoint(client) -> None:
    response = client.post(
        "/api/palettes/analyze", json={"id": "x", "name": "X", "colors": ["#000000", "#ffffff"]}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["color_count"] == 2
    assert body["contrast"]["max_contrast_ratio"] == pytest.approx(21.0)


def test_stored_palette_analysis_endpoint(client) -> None:
    response = client.get("/api/palettes/monochrome-handheld/analysis")
    assert response.status_code == 200
    assert response.json()["color_count"] == 4


def test_compress_endpoint(client) -> None:
    response = client.post(
        "/api/palettes/compress",
        json={
            "palette": {
                "id": "b",
                "name": "B",
                "colors": ["#000000", "#ff0000", "#00ff00", "#ffffff"],
            },
            "target_colors": 2,
        },
    )
    assert response.status_code == 200
    assert len(response.json()["colors"]) <= 2


def test_simulate_cvd_endpoint_and_validation(client) -> None:
    ok = client.post(
        "/api/palettes/simulate-cvd",
        json={
            "palette": {"id": "b", "name": "B", "colors": ["#d02828", "#28a028"]},
            "vision": "deuteranopia",
        },
    )
    assert ok.status_code == 200
    bad = client.post(
        "/api/palettes/simulate-cvd",
        json={"palette": {"id": "b", "name": "B", "colors": ["#000000"]}, "vision": "nope"},
    )
    assert bad.status_code == 422


# --- CLI --------------------------------------------------------------------


def test_cli_palette_analyze(capsys) -> None:
    assert main(["palette", "monochrome-handheld"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["color_count"] == 4
    assert "suggestions" in payload


def test_cli_palette_compress(capsys) -> None:
    assert main(["palette", "8bit-console", "--compress", "4"]) == 0
    assert len(json.loads(capsys.readouterr().out)["colors"]) <= 4


def test_cli_palette_bad_vision_exits_2(capsys) -> None:
    assert main(["palette", "monochrome-handheld", "--simulate", "nope"]) == 2
    assert "unknown vision" in capsys.readouterr().err
