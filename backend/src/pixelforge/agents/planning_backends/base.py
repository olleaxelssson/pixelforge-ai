"""PlanningBackend interface: the agent-runtime analogue of ``GenerationBackend`` (D-010).

An agent asks a backend to produce a structured, schema-validated result. Real backends (Anthropic /
OpenAI / local Ollama, later milestones) send ``system``/``instructions``/``context`` to a model and
parse the JSON reply into the requested pydantic schema. The ``MockPlanningBackend`` instead returns
the agent's ``deterministic`` result verbatim — so the layer is fully testable offline.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TypeVar

from pydantic import BaseModel

ModelT = TypeVar("ModelT", bound=BaseModel)


@dataclass
class AgentCall:
    """One request from an agent to a planning backend.

    ``deterministic`` is the result an offline planner would return for this exact input; it is a
    real, useful heuristic (not a placeholder) that doubles as the mock/offline plan. Real LLM
    backends ignore it and derive the answer from ``system``/``instructions``/``context``.
    """

    agent: str
    deterministic: BaseModel
    system: str = ""
    instructions: str = ""
    context: dict[str, object] = field(default_factory=dict)


class PlanningBackend(ABC):
    name: str = "abstract"

    @abstractmethod
    def is_available(self) -> bool:
        """Whether this backend can run on the current machine/installation."""

    @abstractmethod
    def complete_structured(self, call: AgentCall, schema: type[ModelT]) -> ModelT:
        """Return a validated instance of ``schema`` for the given agent call."""
