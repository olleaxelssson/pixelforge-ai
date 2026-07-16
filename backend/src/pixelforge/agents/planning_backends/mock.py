"""Deterministic, offline planning backend — the CI/default choice (D-004, D-010).

It returns each agent's ``deterministic`` result, re-validated against the requested schema. Because
the agents compute genuinely useful heuristics for that field, the mock backend *is* a real offline
planner: same input, same Scene Graph, no API keys, no network.
"""

from __future__ import annotations

from pixelforge.agents.planning_backends.base import AgentCall, ModelT, PlanningBackend


class MockPlanningBackend(PlanningBackend):
    name = "mock"

    def is_available(self) -> bool:
        return True

    def complete_structured(self, call: AgentCall, schema: type[ModelT]) -> ModelT:
        result = call.deterministic
        if not isinstance(result, schema):
            raise TypeError(
                f"mock planning backend expected {schema.__name__} for agent "
                f"'{call.agent}', got {type(result).__name__}"
            )
        # Round-trip through validation so callers always get a clean, schema-conformant instance.
        return schema.model_validate(result.model_dump())
