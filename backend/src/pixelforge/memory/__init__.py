"""Character memory (D-011): persistent identity so characters don't drift across generations.

A :class:`~pixelforge.memory.models.Character` stores a reusable identity — a Scene-Graph fragment,
a locked palette, reference frames, and an identity embedding. Tier 1 (default, no training) reuses
that identity plus reference-image conditioning; a measured drift gate (embedding cosine similarity)
turns "no identity drift" into an enforced property rather than a hope. Everything here is
deterministic and offline via the mock embedding backend.
"""
