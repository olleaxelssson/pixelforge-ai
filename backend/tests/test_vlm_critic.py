"""VLM / semantic critic tests (D-013): mock backend, blend, engine, gating, registry, API, CLI."""

from __future__ import annotations

import base64
import io
import json

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from pixelforge.cli import main
from pixelforge.config import get_settings
from pixelforge.core.errors import UnknownRegistryKeyError
from pixelforge.qa.critic import HeuristicCritic, VLMCritic
from pixelforge.qa.critic_backends import registry as critic_registry
from pixelforge.qa.critic_backends.base import CriticBackend
from pixelforge.qa.critic_backends.mock import MockCriticBackend
from pixelforge.qa.critic_backends.registry import get_critic_backend, register_critic_backend
from pixelforge.qa.critic_backends.vlm import VLMCriticBackend
from pixelforge.qa.engine import QAEngine
from pixelforge.qa.models import Critique, DetectorContext


def _square(size: int = 16) -> np.ndarray:
    arr = np.zeros((size, size, 4), np.uint8)
    arr[4:12, 4:12] = [200, 40, 40, 255]
    arr[4:8, 4:12] = [230, 90, 90, 255]  # a lighter band → some contrast/readability
    return arr


def _img(arr: np.ndarray) -> Image.Image:
    return Image.fromarray(arr.astype(np.uint8), "RGBA")


@pytest.fixture(autouse=True)
def _isolate_critic_registry():
    """Snapshot/restore the critic-backend registry so registration tests don't leak."""
    snapshot = dict(critic_registry._BACKENDS)
    yield
    critic_registry._BACKENDS.clear()
    critic_registry._BACKENDS.update(snapshot)


# --- mock backend -----------------------------------------------------------


def test_mock_critic_is_deterministic_and_ranged() -> None:
    backend = MockCriticBackend()
    ctx = DetectorContext(subject="a knight")
    first = backend.assess(_square(), ctx)
    second = backend.assess(_square(), ctx)
    assert first == second  # pydantic value-equality → deterministic
    assert 0.0 <= first.subject_match <= 1.0
    assert 0.0 <= first.appeal <= 1.0
    assert "a knight" in first.verdict


def test_mock_critic_neutral_without_subject() -> None:
    critique = MockCriticBackend().assess(_square(), DetectorContext(subject=None))
    assert critique.subject_match == 0.5
    assert any("subject" in note for note in critique.notes)


def test_mock_critic_flags_empty_sprite() -> None:
    empty = np.zeros((16, 16, 4), np.uint8)
    critique = MockCriticBackend().assess(empty, DetectorContext(subject="a knight"))
    assert critique.subject_match == 0.0 and critique.appeal == 0.0


# --- VLMCritic blend --------------------------------------------------------


class _StubBackend(CriticBackend):
    name = "stub"

    def __init__(self, subject_match: float, appeal: float) -> None:
        self._sm = subject_match
        self._ap = appeal

    def assess(self, rgba: np.ndarray, context: DetectorContext) -> Critique:
        return Critique(backend=self.name, subject_match=self._sm, appeal=self._ap)


def test_vlmcritic_folds_subject_match_into_overall() -> None:
    rgba = _square()
    ctx = DetectorContext(subject="a knight")
    high_scores, high_crit = VLMCritic(_StubBackend(1.0, 1.0)).evaluate(rgba, ctx, [])
    low_scores, _ = VLMCritic(_StubBackend(0.0, 0.0)).evaluate(rgba, ctx, [])

    # Same pixels → identical heuristic axes, but semantics move the overall.
    assert high_scores.overall > low_scores.overall
    assert high_scores.readability == low_scores.readability  # pixel axes untouched
    assert high_crit is not None and high_crit.subject_match == 1.0


def test_vlmcritic_score_matches_evaluate() -> None:
    rgba = _square()
    ctx = DetectorContext(subject="a knight")
    critic = VLMCritic(MockCriticBackend())
    assert critic.score(rgba, ctx, []) == critic.evaluate(rgba, ctx, [])[0]


# --- engine integration -----------------------------------------------------


def test_engine_with_vlm_attaches_critique() -> None:
    engine = QAEngine(critic=VLMCritic(MockCriticBackend()))
    report = engine.run(_img(_square()), DetectorContext(subject="a knight"))
    assert report.critique is not None
    assert report.critique.backend == "mock"
    assert report.critique.subject == "a knight"


def test_engine_heuristic_has_no_critique() -> None:
    report = QAEngine(critic=HeuristicCritic()).run(_img(_square()), DetectorContext())
    assert report.critique is None


# --- gating & registry ------------------------------------------------------


def test_vlm_backend_unavailable_without_ml_extra() -> None:
    assert VLMCriticBackend().is_available() is False


def test_registry_auto_falls_back_to_mock() -> None:
    assert get_critic_backend("auto").name == "mock"  # VLM unavailable in CI
    assert get_critic_backend("mock").name == "mock"
    with pytest.raises(UnknownRegistryKeyError):
        get_critic_backend("nope")


def test_register_critic_backend() -> None:
    register_critic_backend(_StubBackend(0.5, 0.5))
    assert get_critic_backend("stub").name == "stub"


# --- API + CLI --------------------------------------------------------------


def _b64(arr: np.ndarray) -> str:
    buffer = io.BytesIO()
    _img(arr).save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()


def test_qa_endpoint_no_critique_under_heuristic(client) -> None:
    response = client.post("/api/qa", json={"image_base64": _b64(_square()), "subject": "a knight"})
    assert response.status_code == 200
    assert response.json()["report"]["critique"] is None


def test_qa_endpoint_returns_critique_under_vlm(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PIXELFORGE_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("PIXELFORGE_BACKEND", "mock")
    monkeypatch.setenv("PIXELFORGE_QA_CRITIC", "vlm")
    get_settings.cache_clear()
    from pixelforge.main import app

    with TestClient(app) as vlm_client:
        response = vlm_client.post(
            "/api/qa", json={"image_base64": _b64(_square()), "subject": "a knight"}
        )
        critique = response.json()["report"]["critique"]
        assert critique is not None and critique["backend"] == "mock"
        assert critique["subject"] == "a knight"
    get_settings.cache_clear()


def test_cli_qa_vlm_critic(tmp_path, capsys) -> None:
    path = tmp_path / "sprite.png"
    _img(_square()).save(path)
    assert main(["qa", str(path), "--critic", "vlm", "--subject", "a knight"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["critique"]["backend"] == "mock"
    assert payload["critique"]["subject"] == "a knight"
