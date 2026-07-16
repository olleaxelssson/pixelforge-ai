"""Planning-backend registry: swap providers by name, mirroring the diffusion-backend registry.

Only the deterministic ``mock`` backend ships in M7. Cloud/local-LLM providers (Anthropic, OpenAI,
Ollama) register here in a later milestone; the interface and selection are ready for them.
"""

from __future__ import annotations

from collections.abc import Callable

from pixelforge.agents.planning_backends.base import PlanningBackend
from pixelforge.agents.planning_backends.mock import MockPlanningBackend
from pixelforge.core.errors import UnknownRegistryKeyError

_BACKENDS: dict[str, Callable[[], PlanningBackend]] = {
    "mock": MockPlanningBackend,
}


def get_planning_backend(name: str) -> PlanningBackend:
    """Return a planning backend by id. ``auto``/empty resolves to the best available (mock)."""
    if name in ("auto", ""):
        name = "mock"
    factory = _BACKENDS.get(name)
    if factory is None:
        raise UnknownRegistryKeyError(f"unknown planning backend: {name}")
    return factory()


def list_planning_backends() -> list[dict[str, object]]:
    return [
        {"id": key, "available": factory().is_available()} for key, factory in _BACKENDS.items()
    ]
