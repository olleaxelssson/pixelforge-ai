"""Agentic planning layer tests (D-010): backend, agents, runtime, compiler, wiring.

All deterministic and offline — the mock planning backend needs no API keys.
"""

from __future__ import annotations

import json

import pytest

from pixelforge.agents.art_director import ArtDirectionResult, ArtDirectorAgent, build_art_direction
from pixelforge.agents.base import PlanningContext
from pixelforge.agents.intent import IntentAgent, IntentResult, build_intent_result
from pixelforge.agents.planning_backends.mock import MockPlanningBackend
from pixelforge.agents.planning_backends.registry import (
    get_planning_backend,
    list_planning_backends,
)
from pixelforge.agents.registry import AgentRegistry
from pixelforge.agents.runtime import PlanningRuntime
from pixelforge.cli import main
from pixelforge.core.models import GenerationRequest
from pixelforge.core.scene_graph import CameraPerspective, EntityKind, MaterialKind
from pixelforge.generation.pipeline import GenerationPipeline
from pixelforge.generation.plan_compiler import compile_negative_prompt, compile_prompt
from pixelforge.modes.registry import ModeRegistry
from pixelforge.palettes.service import PaletteService
from pixelforge.styles.registry import StyleRegistry

_KNIGHT = "red knight with a flaming sword"


def _runtime(backend_name: str = "mock") -> PlanningRuntime:
    return PlanningRuntime(
        backend=get_planning_backend(backend_name), modes=ModeRegistry(), styles=StyleRegistry()
    )


def _context(prompt: str = _KNIGHT, mode: str = "character", style: str = "nes-inspired"):
    request = GenerationRequest(prompt=prompt, mode=mode, style=style, seed=1)
    return PlanningContext(
        request=request, mode=ModeRegistry().get(mode), style=StyleRegistry().get(style)
    )


# --- planning backend -------------------------------------------------------


def test_mock_backend_returns_deterministic_field() -> None:
    result = MockPlanningBackend().complete_structured(
        IntentAgent().build_call(_context()), IntentResult
    )
    assert isinstance(result, IntentResult)
    assert result.entity.subject == _KNIGHT


def test_mock_backend_type_mismatch_raises() -> None:
    with pytest.raises(TypeError):
        MockPlanningBackend().complete_structured(
            IntentAgent().build_call(_context()), ArtDirectionResult
        )


def test_list_planning_backends() -> None:
    assert {"id": "mock", "available": True} in list_planning_backends()


def test_unknown_planning_backend_rejected() -> None:
    from pixelforge.core.errors import UnknownRegistryKeyError

    with pytest.raises(UnknownRegistryKeyError):
        get_planning_backend("does-not-exist")


# --- agents -----------------------------------------------------------------


def test_intent_parses_entity_parts_and_materials() -> None:
    result = build_intent_result(_context())
    assert result.entity.kind is EntityKind.CHARACTER
    part_names = [p.name for p in result.entity.parts]
    assert "body" in part_names and "blade" in part_names
    material_kinds = {m.kind for m in result.entity.materials}
    assert MaterialKind.METAL in material_kinds and MaterialKind.ENERGY in material_kinds


def test_intent_generic_kind_for_free_form_mode() -> None:
    result = build_intent_result(_context(prompt="a mysterious rune", mode="text-to-pixel"))
    assert result.entity.kind is EntityKind.GENERIC


def test_art_director_sets_camera_from_kind() -> None:
    context = _context(prompt="great sword", mode="weapon")
    context.outputs["intent"] = build_intent_result(context)
    assert build_art_direction(context).camera.perspective is CameraPerspective.THREE_QUARTER


def test_art_director_locks_requested_palette() -> None:
    request = GenerationRequest(prompt="hero", mode="character", palette_id="some-palette")
    context = PlanningContext(
        request=request,
        mode=ModeRegistry().get("character"),
        style=StyleRegistry().get("modern-indie"),
    )
    context.outputs["intent"] = build_intent_result(context)
    palette = build_art_direction(context).palette
    assert palette.locked and palette.palette_id == "some-palette"


# --- runtime ----------------------------------------------------------------


def test_runtime_produces_scene_graph_with_trace() -> None:
    graph = _runtime().plan(GenerationRequest(prompt=_KNIGHT, mode="character", seed=1))
    assert graph.entity.kind is EntityKind.CHARACTER
    assert graph.provenance.agent_trace == ["intent", "art-director"]
    assert graph.provenance.planning_backend == "mock"


def test_runtime_is_deterministic() -> None:
    runtime = _runtime()
    request = GenerationRequest(prompt="slime", mode="creature", seed=3)
    first, second = runtime.plan(request), runtime.plan(request)
    assert first.id == second.id
    assert first.canonical_json() == second.canonical_json()


def test_runtime_cache_returns_independent_copies() -> None:
    runtime = _runtime()
    request = GenerationRequest(prompt="orc", seed=2)
    first = runtime.plan(request)
    first.entity.subject = "mutated"
    assert runtime.plan(request).entity.subject == "orc"


def test_runtime_orders_by_dependencies_regardless_of_registry_order() -> None:
    runtime = PlanningRuntime(
        backend=get_planning_backend("mock"),
        modes=ModeRegistry(),
        styles=StyleRegistry(),
        agents=AgentRegistry([ArtDirectorAgent(), IntentAgent()]),
    )
    graph = runtime.plan(GenerationRequest(prompt="knight", mode="character", seed=1))
    assert graph.provenance.agent_trace == ["intent", "art-director"]


# --- compiler ---------------------------------------------------------------


def test_compile_prompt_traces_the_plan() -> None:
    graph = _runtime().plan(
        GenerationRequest(prompt=_KNIGHT, mode="character", style="nes-inspired", seed=1)
    )
    prompt = compile_prompt(graph, StyleRegistry().get("nes-inspired"))
    assert _KNIGHT in prompt
    assert "front view" in prompt
    assert "light source from top-left" in prompt
    assert "isolated on plain solid background" in prompt
    assert "8-bit pixel art" in prompt  # style prefix


def test_compile_negative_prompt_dedupes_terms() -> None:
    graph = _runtime().plan(
        GenerationRequest(prompt="knight", mode="character", style="nes-inspired", seed=1)
    )
    negative = compile_negative_prompt(graph, StyleRegistry().get("nes-inspired"))
    terms = [t.strip() for t in negative.split(",")]
    assert terms == list(dict.fromkeys(terms))  # no duplicates, order preserved
    assert "blurry" in terms


# --- pipeline integration ---------------------------------------------------


def test_pipeline_with_planner_generates(tmp_path) -> None:
    modes, styles = ModeRegistry(), StyleRegistry()
    pipeline = GenerationPipeline(
        backend_name="mock",
        outputs_dir=tmp_path,
        modes=modes,
        styles=styles,
        palettes=PaletteService(user_dir=tmp_path / "palettes"),
        diffusion_resolution=128,
        planner=PlanningRuntime(backend=get_planning_backend("mock"), modes=modes, styles=styles),
    )
    request = GenerationRequest(prompt=_KNIGHT, mode="character", width=16, height=16, seed=1)
    result = pipeline.run("planjob", request, lambda stage, pct: None)
    assert len(result.images) == 1


# --- API + CLI --------------------------------------------------------------


def test_plan_endpoint(client) -> None:
    response = client.post(
        "/api/plan",
        json={"prompt": _KNIGHT, "mode": "character", "style": "nes-inspired", "seed": 1},
    )
    assert response.status_code == 200
    graph = response.json()
    assert graph["entity"]["kind"] == "character"
    assert _KNIGHT in graph["provenance"]["expanded_prompt"]


def test_plan_endpoint_rejects_unknown_style(client) -> None:
    assert client.post("/api/plan", json={"prompt": "x", "style": "nope"}).status_code == 422


def test_cli_plan(capsys) -> None:
    code = main(["plan", _KNIGHT, "--mode", "character", "--style", "nes-inspired", "--seed", "1"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["entity"]["kind"] == "character"
    assert _KNIGHT in payload["provenance"]["expanded_prompt"]


def test_cli_list_planning_backends(capsys) -> None:
    assert main(["list", "planning-backends"]) == 0
    assert json.loads(capsys.readouterr().out)[0]["id"] == "mock"
