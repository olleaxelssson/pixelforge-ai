"""Scene Graph model tests (D-009): determinism, hashing, migration, schema export."""

from __future__ import annotations

import pytest

from pixelforge.core.scene_graph import (
    SCENE_GRAPH_SCHEMA_VERSION,
    Constraints,
    Entity,
    EntityKind,
    SceneGraph,
    scene_graph_from_dict,
    scene_graph_json_schema,
)


def _graph() -> SceneGraph:
    return SceneGraph(entity=Entity(kind=EntityKind.CHARACTER, subject="knight"))


def test_defaults_and_schema_version() -> None:
    graph = _graph()
    assert graph.schema_version == SCENE_GRAPH_SCHEMA_VERSION
    assert graph.constraints == Constraints()
    assert graph.entity.subject == "knight"


def test_canonical_json_is_deterministic() -> None:
    graph = _graph()
    graph.id = "fixed"
    assert graph.canonical_json() == graph.model_copy(deep=True).canonical_json()


def test_content_hash_ignores_id_and_provenance() -> None:
    a, b = _graph(), _graph()
    a.id, b.id = "aaa", "bbb"
    b.provenance.user_prompt = "an unrelated note"
    assert a.content_hash() == b.content_hash()


def test_content_hash_changes_with_semantics() -> None:
    a, b = _graph(), _graph()
    b.entity.subject = "wizard"
    assert a.content_hash() != b.content_hash()


def test_round_trip_from_dict() -> None:
    graph = _graph()
    restored = scene_graph_from_dict(graph.canonical_dict())
    assert restored.canonical_json() == graph.canonical_json()


def test_newer_schema_version_is_rejected() -> None:
    data = _graph().canonical_dict()
    data["schema_version"] = SCENE_GRAPH_SCHEMA_VERSION + 1
    with pytest.raises(ValueError, match="newer than supported"):
        scene_graph_from_dict(data)


def test_json_schema_exports_top_level_fields() -> None:
    schema = scene_graph_json_schema()
    assert "entity" in schema["properties"]
    assert "provenance" in schema["properties"]
    assert "constraints" in schema["properties"]
