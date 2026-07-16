"""Planning runtime: order agents, run them, and assemble a Scene Graph (D-010).

The runtime topologically orders agents by their declared dependencies, runs each against the chosen
planning backend, and folds their typed outputs into a :class:`SceneGraph`. Results are cached by
request content so re-planning and edits are cheap. Execution is sequential in dependency order;
independent agents could be run concurrently in a later optimization without changing this contract.
"""

from __future__ import annotations

import hashlib
import json
from collections import OrderedDict

from pixelforge.agents.art_director import ArtDirectionResult
from pixelforge.agents.base import Agent, PlanningContext
from pixelforge.agents.intent import IntentResult
from pixelforge.agents.planning_backends.base import PlanningBackend
from pixelforge.agents.registry import AgentRegistry
from pixelforge.core.models import GenerationRequest
from pixelforge.core.scene_graph import Provenance, SceneGraph
from pixelforge.modes.registry import ModeRegistry
from pixelforge.styles.registry import StyleRegistry


class PlanningRuntime:
    def __init__(
        self,
        backend: PlanningBackend,
        modes: ModeRegistry,
        styles: StyleRegistry,
        agents: AgentRegistry | None = None,
        cache_size: int = 128,
    ) -> None:
        self._backend = backend
        self._modes = modes
        self._styles = styles
        self._agents = agents or AgentRegistry()
        self._cache: OrderedDict[str, SceneGraph] = OrderedDict()
        self._cache_size = cache_size

    def plan(self, request: GenerationRequest) -> SceneGraph:
        key = self._cache_key(request)
        cached = self._cache.get(key)
        if cached is not None:
            self._cache.move_to_end(key)
            return cached.model_copy(deep=True)

        mode = self._modes.get(request.mode)
        style = self._styles.get(request.style)
        context = PlanningContext(request=request, mode=mode, style=style)
        trace: list[str] = []
        for agent in self._ordered_agents():
            context.outputs[agent.name] = agent.run(context, self._backend)
            trace.append(agent.name)

        graph = self._assemble(context, trace)
        self._store(key, graph)
        return graph.model_copy(deep=True)

    def _assemble(self, context: PlanningContext, trace: list[str]) -> SceneGraph:
        request = context.request
        intent = context.output("intent", IntentResult)
        art = context.output("art-director", ArtDirectionResult)
        graph = SceneGraph(
            entity=intent.entity,
            palette=art.palette,
            lighting=art.lighting,
            camera=art.camera,
            pose=art.pose,
            constraints=intent.constraints,
            tags=intent.tags,
            provenance=Provenance(
                user_prompt=request.prompt,
                negative_prompt=request.negative_prompt,
                seed=request.seed,
                mode=request.mode,
                style=request.style,
                planning_backend=self._backend.name,
                agent_trace=trace,
            ),
        )
        # A content-derived id makes planning deterministic: identical requests yield identical ids.
        graph.id = graph.content_hash()
        return graph

    def _ordered_agents(self) -> list[Agent]:
        agents = {a.name: a for a in self._agents.list()}
        ordered: list[Agent] = []
        visited: set[str] = set()
        visiting: set[str] = set()

        def visit(agent: Agent) -> None:
            if agent.name in visited:
                return
            if agent.name in visiting:
                raise ValueError(f"cycle in agent dependencies at '{agent.name}'")
            visiting.add(agent.name)
            for dependency in agent.dependencies:
                if dependency in agents:
                    visit(agents[dependency])
            visiting.discard(agent.name)
            visited.add(agent.name)
            ordered.append(agent)

        for agent in self._agents.list():
            visit(agent)
        return ordered

    def _cache_key(self, request: GenerationRequest) -> str:
        payload = {"request": request.model_dump(mode="json"), "backend": self._backend.name}
        blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    def _store(self, key: str, graph: SceneGraph) -> None:
        self._cache[key] = graph
        self._cache.move_to_end(key)
        while len(self._cache) > self._cache_size:
            self._cache.popitem(last=False)
