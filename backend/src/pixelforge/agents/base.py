"""Agent base class and the planning context passed between agents (D-010).

An agent has one responsibility. It reads the :class:`PlanningContext` (the request, the resolved
mode/style, and any prior agents' outputs) and produces a single validated pydantic result via a
:class:`PlanningBackend`. Agents never emit free text into the pipeline — only typed objects.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TypeVar

from pydantic import BaseModel

from pixelforge.agents.planning_backends.base import AgentCall, PlanningBackend
from pixelforge.core.models import GenerationRequest
from pixelforge.modes.registry import GenerationMode
from pixelforge.styles.model import StylePreset

T = TypeVar("T", bound=BaseModel)


@dataclass
class PlanningContext:
    """Shared, evolving state for one planning run."""

    request: GenerationRequest
    mode: GenerationMode
    style: StylePreset
    outputs: dict[str, BaseModel] = field(default_factory=dict)

    def output(self, agent_name: str, schema: type[T]) -> T:
        """Fetch a prior agent's output, typed. Raises if missing or the wrong type."""
        value = self.outputs.get(agent_name)
        if value is None:
            raise KeyError(f"agent '{agent_name}' has not produced an output yet")
        if not isinstance(value, schema):
            raise TypeError(
                f"expected {schema.__name__} from agent '{agent_name}', got {type(value).__name__}"
            )
        return value


class Agent(ABC):
    name: str = "abstract"
    output_model: type[BaseModel]
    dependencies: tuple[str, ...] = ()

    @abstractmethod
    def build_call(self, context: PlanningContext) -> AgentCall:
        """Construct the backend call, including the deterministic offline result."""

    def run(self, context: PlanningContext, backend: PlanningBackend) -> BaseModel:
        return backend.complete_structured(self.build_call(context), self.output_model)
