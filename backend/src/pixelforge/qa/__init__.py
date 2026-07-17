"""Pixel QA engine (D-013): deterministic defect detectors + a heuristic critic.

Two layers, both mock-free and deterministic in M9:

- **Detectors** (`detectors/`) inspect an RGBA sprite and emit typed
  :class:`~pixelforge.core.scene_graph.Finding` objects; some offer a safe auto-repair.
- **Critic** (`critic.py`) scores the sprite on readability / palette / contrast / silhouette /
  cleanliness, reusing the palette intelligence from D-012.

The :class:`~pixelforge.qa.engine.QAEngine` runs the detectors, scores the result, and can apply the
safe repairs. Findings are shaped to drop straight into ``SceneGraph.qa``.
"""
