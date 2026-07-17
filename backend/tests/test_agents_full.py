"""M11 tests: the full planning agent set, Scene Graph v2 migration, control map, provenance.

All deterministic and offline — the mock planning backend needs no API keys.
"""

from __future__ import annotations

import json

import pytest

from pixelforge.agents.animation import build_animation_plan
from pixelforge.agents.art_director import build_art_direction
from pixelforge.agents.base import PlanningContext
from pixelforge.agents.composition import build_composition
from pixelforge.agents.intent import build_intent_result
from pixelforge.agents.lighting import build_lighting_plan
from pixelforge.agents.material import build_material_plan
from pixelforge.agents.planning_backends.registry import get_planning_backend
from pixelforge.agents.runtime import PlanningRuntime
from pixelforge.agents.silhouette import GRID_SIZE, build_silhouette
from pixelforge.core.models import GenerationRequest
from pixelforge.core.scene_graph import (
    SCENE_GRAPH_SCHEMA_VERSION,
    Entity,
    EntityKind,
    SceneGraph,
    scene_graph_from_dict,
)
from pixelforge.generation.pipeline import GenerationPipeline
from pixelforge.generation.plan_compiler import compile_prompt, compile_silhouette_map
from pixelforge.modes.registry import ModeRegistry
from pixelforge.palettes.service import PaletteService
from pixelforge.styles.registry import StyleRegistry


def _context(prompt: str, mode: str = "character", style: str = "modern-indie") -> PlanningContext:
    request = GenerationRequest(prompt=prompt, mode=mode, style=style, seed=1)
    context = PlanningContext(
        request=request, mode=ModeRegistry().get(mode), style=StyleRegistry().get(style)
    )
    context.outputs["intent"] = build_intent_result(context)
    context.outputs["art-director"] = build_art_direction(context)
    return context


def _runtime() -> PlanningRuntime:
    return PlanningRuntime(
        backend=get_planning_backend("mock"), modes=ModeRegistry(), styles=StyleRegistry()
    )


# --- schema v2 --------------------------------------------------------------


def test_v1_scene_graph_migrates_to_v2() -> None:
    v1 = SceneGraph(entity=Entity(subject="knight")).canonical_dict()
    v1["schema_version"] = 1
    del v1["composition"]
    del v1["silhouette"]
    del v1["lighting"]["rim_light"]
    for material in v1["entity"]["materials"]:
        del material["specular"], material["dither_ok"], material["ramp_size"]
    restored = scene_graph_from_dict(v1)
    assert restored.schema_version == SCENE_GRAPH_SCHEMA_VERSION == 2
    assert restored.composition.framing == "centered"
    assert restored.silhouette is None
    assert restored.lighting.rim_light is False


# --- individual planners ----------------------------------------------------


def test_composition_margins_and_glow_on_top() -> None:
    context = _context("red knight with a flaming sword")
    result = build_composition(context)
    assert result.composition.focal_point == "upper third (face)"
    assert result.part_z_orders["glow"] == max(result.part_z_orders.values())

    tile = _context("grass", mode="tileset")
    assert build_composition(tile).composition.framing == "edge-to-edge"
    assert build_composition(tile).composition.margin_fraction == 0.0


def test_silhouette_shapes_by_kind() -> None:
    knight = _context("knight")
    knight.outputs["composition"] = build_composition(knight)
    grid = build_silhouette(knight).silhouette.grid
    assert len(grid) == GRID_SIZE and all(len(row) == GRID_SIZE for row in grid)
    head_width = grid[3].count("1")
    torso_width = grid[7].count("1")
    assert 0 < head_width < torso_width  # narrow head over wider torso

    tile = _context("grass", mode="tileset")
    tile.outputs["composition"] = build_composition(tile)
    assert all(set(row) == {"1"} for row in build_silhouette(tile).silhouette.grid)


def test_lighting_rim_light_for_energy_materials() -> None:
    flaming = _context("flaming sword hero")
    assert build_lighting_plan(flaming).lighting.rim_light is True
    plain = _context("plain farmer")
    assert build_lighting_plan(plain).lighting.rim_light is False


def test_material_finish_hints() -> None:
    context = _context("knight with a steel sword and wool cloak")
    materials = {m.kind.value: m for m in build_material_plan(context).materials}
    assert materials["metal"].specular is True and materials["metal"].dither_ok is False
    assert materials["cloth"].specular is False and materials["cloth"].dither_ok is True


def test_animation_keyword_detection_and_static_kinds() -> None:
    attacking = _context("knight attacking with a sword")
    plan = build_animation_plan(attacking).animation
    assert plan is not None and plan.action == "attack"

    idle = build_animation_plan(_context("calm knight")).animation
    assert idle is not None and idle.action == "idle"

    facing = build_animation_plan(_context("knight walking facing left")).animation
    assert facing is not None and facing.action == "walk" and facing.direction == "west"

    item = _context("health potion", mode="item")
    assert build_animation_plan(item).animation is None


# --- assembled graph + compiler ---------------------------------------------


def test_full_plan_populates_v2_slots_and_stays_deterministic() -> None:
    runtime = _runtime()
    request = GenerationRequest(
        prompt="red knight attacking with a flaming sword", seed=42, mode="character"
    )
    graph = runtime.plan(request)
    assert graph.silhouette is not None
    assert graph.lighting.rim_light is True
    assert graph.animation is not None and graph.animation.action == "attack"
    assert any(m.specular for m in graph.entity.materials)
    assert graph.id == runtime.plan(request).id


def test_compile_prompt_includes_m11_phrases() -> None:
    graph = _runtime().plan(
        GenerationRequest(
            prompt="red knight attacking with a flaming sword", mode="character", seed=1
        )
    )
    prompt = compile_prompt(graph, StyleRegistry().get("nes-inspired"))
    assert "attack windup" in prompt  # animation frame description
    assert "subtle rim light" in prompt
    assert "sharp single-pixel specular highlights" in prompt
    assert "clear margin around the subject" in prompt


def test_compile_silhouette_map_renders_and_scales() -> None:
    graph = _runtime().plan(GenerationRequest(prompt="knight", mode="character", seed=1))
    image = compile_silhouette_map(graph, 64)
    assert image is not None and image.size == (64, 64) and image.mode == "L"
    values = set(image.getdata())
    assert values <= {0, 255} and values == {0, 255}  # binary mask with both classes


def test_compile_silhouette_map_none_without_plan() -> None:
    graph = SceneGraph(entity=Entity(kind=EntityKind.CHARACTER, subject="x"))
    assert compile_silhouette_map(graph, 64) is None


# --- pipeline: control map + provenance sidecar -----------------------------


def _pipeline(tmp_path, planner: bool):
    modes, styles = ModeRegistry(), StyleRegistry()
    runtime = (
        PlanningRuntime(backend=get_planning_backend("mock"), modes=modes, styles=styles)
        if planner
        else None
    )
    return GenerationPipeline(
        backend_name="mock",
        outputs_dir=tmp_path,
        modes=modes,
        styles=styles,
        palettes=PaletteService(user_dir=tmp_path / "palettes"),
        diffusion_resolution=128,
        planner=runtime,
    )


def test_pipeline_writes_provenance_sidecar_when_planning(tmp_path) -> None:
    request = GenerationRequest(
        prompt="knight attacking", mode="character", width=16, height=16, seed=7
    )
    result = _pipeline(tmp_path, planner=True).run("job", request, lambda s, p: None)
    sidecar_path = tmp_path / "job_0.provenance.json"
    assert sidecar_path.exists()
    sidecar = json.loads(sidecar_path.read_text())
    assert sidecar["generation"]["filename"] == result.images[0].filename
    assert sidecar["generation"]["seed"] == 7
    assert sidecar["scene_graph"]["schema_version"] == 2
    assert sidecar["scene_graph"]["provenance"]["expanded_prompt"]
    assert sidecar["scene_graph"]["provenance"]["model_versions"]["diffusion_backend"] == "mock"


def test_pipeline_fast_path_writes_no_sidecar(tmp_path) -> None:
    request = GenerationRequest(prompt="knight", width=16, height=16, seed=7)
    _pipeline(tmp_path, planner=False).run("fast", request, lambda s, p: None)
    assert not list(tmp_path.glob("*.provenance.json"))


def test_pipeline_passes_silhouette_control_map(tmp_path, monkeypatch) -> None:
    captured: dict[str, object] = {}
    from pixelforge.generation.backends.mock import MockBackend

    original = MockBackend.generate

    def spy(self, spec, on_progress):
        captured.update(spec.extra)
        return original(self, spec, on_progress)

    monkeypatch.setattr(MockBackend, "generate", spy)
    request = GenerationRequest(prompt="knight", mode="character", width=16, height=16, seed=1)
    _pipeline(tmp_path, planner=True).run("cm", request, lambda s, p: None)
    assert "silhouette_map" in captured
    control = captured["silhouette_map"]
    assert getattr(control, "size", None) == (128, 128)


def test_trimmed_registry_still_assembles(tmp_path) -> None:
    # A registry without the M11 planners (as plugins or tests may configure) must still plan.
    from pixelforge.agents.art_director import ArtDirectorAgent
    from pixelforge.agents.intent import IntentAgent
    from pixelforge.agents.registry import AgentRegistry

    runtime = PlanningRuntime(
        backend=get_planning_backend("mock"),
        modes=ModeRegistry(),
        styles=StyleRegistry(),
        agents=AgentRegistry([IntentAgent(), ArtDirectorAgent()]),
    )
    graph = runtime.plan(GenerationRequest(prompt="knight", mode="character", seed=1))
    assert graph.silhouette is None
    assert graph.provenance.agent_trace == ["intent", "art-director"]


def test_pipeline_with_full_planner_generates(tmp_path) -> None:
    request = GenerationRequest(
        prompt="red knight attacking with a flaming sword",
        mode="character",
        width=16,
        height=16,
        seed=1,
        batch_size=2,
    )
    result = _pipeline(tmp_path, planner=True).run("full", request, lambda s, p: None)
    assert len(result.images) == 2
    assert len(list(tmp_path.glob("*.provenance.json"))) == 2


@pytest.mark.parametrize("mode", ["weapon", "item", "tileset", "portrait"])
def test_all_kinds_plan_without_error(mode: str) -> None:
    graph = _runtime().plan(GenerationRequest(prompt="subject", mode=mode, seed=1))
    assert graph.silhouette is not None
