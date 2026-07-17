"""Agent registry: the set of planning agents, extended by adding entries (D-005/D-010).

New agents (composition, silhouette, lighting, material, animation planners in later milestones)
register here; the runtime orders them by their declared dependencies.
"""

from __future__ import annotations

from pixelforge.agents.animation import AnimationAgent
from pixelforge.agents.art_director import ArtDirectorAgent
from pixelforge.agents.base import Agent
from pixelforge.agents.composition import CompositionAgent
from pixelforge.agents.intent import IntentAgent
from pixelforge.agents.lighting import LightingAgent
from pixelforge.agents.material import MaterialAgent
from pixelforge.agents.silhouette import SilhouetteAgent
from pixelforge.core.errors import UnknownRegistryKeyError

BUILTIN_AGENTS: list[Agent] = [
    IntentAgent(),
    ArtDirectorAgent(),
    CompositionAgent(),
    SilhouetteAgent(),
    LightingAgent(),
    MaterialAgent(),
    AnimationAgent(),
]


class AgentRegistry:
    def __init__(self, agents: list[Agent] | None = None) -> None:
        chosen = agents if agents is not None else BUILTIN_AGENTS
        self._agents: dict[str, Agent] = {a.name: a for a in chosen}

    def list(self) -> list[Agent]:
        return list(self._agents.values())

    def get(self, name: str) -> Agent:
        agent = self._agents.get(name)
        if agent is None:
            raise UnknownRegistryKeyError(f"unknown agent: {name}")
        return agent
