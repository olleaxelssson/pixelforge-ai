"""Character-memory tests (D-011): embeddings, drift gate, store, identity application, API, CLI.

All deterministic and offline via the mock embedding backend — no weights, no keys.
"""

from __future__ import annotations

import base64
import io
import json

import numpy as np
import pytest
from PIL import Image

from pixelforge.cli import main
from pixelforge.core.errors import UnknownRegistryKeyError
from pixelforge.core.models import GenerationRequest
from pixelforge.memory.drift import cosine_similarity
from pixelforge.memory.embeddings import MockEmbeddingBackend, get_embedding_backend
from pixelforge.memory.models import CharacterIdentity
from pixelforge.memory.service import CharacterMemory
from pixelforge.memory.store import CharacterStore


def _knight(color=(200, 40, 40)) -> Image.Image:
    arr = np.zeros((32, 32, 4), np.uint8)
    arr[8:28, 10:22] = [*color, 255]  # body
    arr[4:8, 12:20] = [240, 210, 170, 255]  # head
    return Image.fromarray(arr, "RGBA")


def _slime() -> Image.Image:
    arr = np.zeros((32, 32, 4), np.uint8)
    arr[16:30, 4:28] = [40, 200, 80, 255]
    return Image.fromarray(arr, "RGBA")


def _memory(tmp_path) -> CharacterMemory:
    return CharacterMemory(
        store=CharacterStore(characters_dir=tmp_path / "characters"),
        embeddings=MockEmbeddingBackend(),
        drift_threshold=0.85,
    )


def _identity() -> CharacterIdentity:
    return CharacterIdentity(
        subject="Captain Elias, a grizzled veteran knight",
        proportions="tall, broad-shouldered",
        silhouette="horned helm, long cape",
    )


# --- embeddings + drift metric ----------------------------------------------


def test_mock_embedding_is_deterministic_and_normalized() -> None:
    backend = MockEmbeddingBackend()
    a, b = backend.embed(_knight()), backend.embed(_knight())
    assert a == b
    assert np.linalg.norm(a) == pytest.approx(1.0, abs=1e-9)


def test_similar_images_score_higher_than_different() -> None:
    backend = MockEmbeddingBackend()
    knight = backend.embed(_knight())
    tinted = backend.embed(_knight(color=(210, 50, 50)))  # same pose, slightly different tint
    slime = backend.embed(_slime())
    assert cosine_similarity(knight, tinted) > cosine_similarity(knight, slime)


def test_cosine_similarity_edges() -> None:
    assert cosine_similarity([], [1.0]) == 0.0
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)


def test_unknown_embedding_backend_rejected() -> None:
    with pytest.raises(UnknownRegistryKeyError):
        get_embedding_backend("nope")


# --- store + service ---------------------------------------------------------


def test_create_get_list_delete(tmp_path) -> None:
    memory = _memory(tmp_path)
    character = memory.create("Elias", _identity(), palette_id="8bit-console")
    assert memory.get(character.id).name == "Elias"
    assert [c.id for c in memory.list()] == [character.id]
    assert memory.delete(character.id)
    with pytest.raises(UnknownRegistryKeyError):
        memory.get(character.id)


def test_reference_frame_anchors_embedding(tmp_path) -> None:
    memory = _memory(tmp_path)
    character = memory.create("Elias", _identity())
    assert character.embedding == []
    character = memory.add_reference_frame(character.id, _knight(), label="passport")
    assert character.embedding
    assert character.canonical_frame() is not None
    assert character.canonical_frame().label == "passport"


def test_drift_gate_accepts_same_rejects_different(tmp_path) -> None:
    memory = _memory(tmp_path)
    character = memory.create("Elias", _identity())
    memory.add_reference_frame(character.id, _knight(), label="passport")

    same = memory.check_drift(character.id, _knight())
    assert same.consistent and same.similarity == pytest.approx(1.0, abs=1e-6)

    different = memory.check_drift(character.id, _slime())
    assert not different.consistent
    assert different.similarity < same.similarity


def test_drift_without_frames_raises(tmp_path) -> None:
    memory = _memory(tmp_path)
    character = memory.create("Elias", _identity())
    with pytest.raises(ValueError, match="no reference frame"):
        memory.check_drift(character.id, _knight())


def test_apply_to_request_injects_identity(tmp_path) -> None:
    memory = _memory(tmp_path)
    character = memory.create("Elias", _identity(), palette_id="8bit-console")
    memory.add_reference_frame(character.id, _knight(), label="passport")

    request = GenerationRequest(prompt="winter armor", seed=7)
    applied = memory.apply_to_request(character.id, request)

    assert applied.prompt.startswith("Captain Elias")
    assert "winter armor" in applied.prompt
    assert applied.mode == "character"
    assert applied.palette_id == "8bit-console"
    assert applied.reference_image_base64  # canonical frame attached
    assert applied.seed == 7
    assert request.prompt == "winter armor"  # original untouched


def test_apply_identity_is_stable_across_variations(tmp_path) -> None:
    """'Elias winter armor' and 'Elias without helmet' share the same identity prefix."""
    memory = _memory(tmp_path)
    character = memory.create("Elias", _identity())
    winter = memory.apply_to_request(character.id, GenerationRequest(prompt="winter armor"))
    helmetless = memory.apply_to_request(character.id, GenerationRequest(prompt="without helmet"))
    prefix = memory.identity_phrase(memory.get(character.id))
    assert winter.prompt.startswith(prefix)
    assert helmetless.prompt.startswith(prefix)


def test_apply_respects_explicit_palette(tmp_path) -> None:
    memory = _memory(tmp_path)
    character = memory.create("Elias", _identity(), palette_id="8bit-console")
    applied = memory.apply_to_request(
        character.id, GenerationRequest(prompt="x", palette_id="monochrome-handheld")
    )
    assert applied.palette_id == "monochrome-handheld"  # user's choice wins


# --- API ---------------------------------------------------------------------


def _b64(image: Image.Image) -> str:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()


def test_character_api_flow(client) -> None:
    created = client.post(
        "/api/characters",
        json={"name": "Elias", "identity": {"subject": "Captain Elias, veteran knight"}},
    )
    assert created.status_code == 200
    character_id = created.json()["id"]

    framed = client.post(
        f"/api/characters/{character_id}/frames",
        json={"image_base64": _b64(_knight()), "label": "passport"},
    )
    assert framed.status_code == 200
    assert framed.json()["embedding"]

    same = client.post(
        f"/api/characters/{character_id}/drift", json={"image_base64": _b64(_knight())}
    )
    assert same.status_code == 200 and same.json()["consistent"] is True

    drifted = client.post(
        f"/api/characters/{character_id}/drift", json={"image_base64": _b64(_slime())}
    )
    assert drifted.status_code == 200 and drifted.json()["consistent"] is False

    assert client.get(f"/api/characters/{character_id}").status_code == 200
    assert client.delete(f"/api/characters/{character_id}").json()["deleted"]


def test_character_api_404s(client) -> None:
    assert client.get("/api/characters/nope").status_code == 404
    assert (
        client.post(
            "/api/characters/nope/drift", json={"image_base64": _b64(_knight())}
        ).status_code
        == 404
    )


def test_generate_with_character_applies_identity(client) -> None:
    created = client.post(
        "/api/characters",
        json={"name": "Elias", "identity": {"subject": "Captain Elias, veteran knight"}},
    )
    character_id = created.json()["id"]
    response = client.post(
        "/api/generate",
        json={"prompt": "winter armor", "character_id": character_id, "seed": 1},
    )
    assert response.status_code == 202
    assert response.json()["request"]["prompt"].startswith("Captain Elias")


def test_generate_with_unknown_character_rejected(client) -> None:
    response = client.post("/api/generate", json={"prompt": "x", "character_id": "nope"})
    assert response.status_code == 422


# --- CLI ---------------------------------------------------------------------


def test_cli_character_create_frame_drift(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("PIXELFORGE_DATA_DIR", str(tmp_path))
    from pixelforge.config import get_settings

    get_settings.cache_clear()
    try:
        assert (
            main(["character", "create", "Elias", "--subject", "Captain Elias, veteran knight"])
            == 0
        )
        character_id = json.loads(capsys.readouterr().out)["id"]

        frame = tmp_path / "passport.png"
        _knight().save(frame)
        assert main(["character", "add-frame", character_id, str(frame)]) == 0
        assert json.loads(capsys.readouterr().out)["embedding"]

        candidate = tmp_path / "candidate.png"
        _slime().save(candidate)
        assert main(["character", "drift", character_id, str(candidate)]) == 0
        assert json.loads(capsys.readouterr().out)["consistent"] is False

        assert main(["character", "list"]) == 0
        assert len(json.loads(capsys.readouterr().out)) == 1
    finally:
        get_settings.cache_clear()
