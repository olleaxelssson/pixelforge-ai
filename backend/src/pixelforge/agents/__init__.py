"""The agentic planning layer (D-010): single-responsibility agents that build a Scene Graph.

Agents *plan and critique*; the deterministic pipeline *executes*. Each agent reads the evolving
:class:`~pixelforge.core.scene_graph.SceneGraph`/context and emits a validated, typed result via a
swappable :class:`~pixelforge.agents.planning_backends.base.PlanningBackend`. The whole layer runs
in CI against the deterministic ``MockPlanningBackend`` with no API keys.
"""
