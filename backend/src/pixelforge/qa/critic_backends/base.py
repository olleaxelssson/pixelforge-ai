"""Critic backend interface (D-013 Layer 2): pluggable semantic/perceptual judgment.

A critic *backend* looks at a finished sprite and its intended subject and returns a
:class:`~pixelforge.qa.models.Critique` — does it read as what was asked for, is it appealing, any
notes. The deterministic mock runs in CI; a real vision-language model implements the same interface
behind an availability gate (like the FLUX generation backend). Swapped in via the registry.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np

from pixelforge.qa.models import Critique, DetectorContext


class CriticBackend(ABC):
    name: str = "abstract"

    def is_available(self) -> bool:
        """Whether this backend can run here. Overridden by backends with heavy/optional deps."""
        return True

    @abstractmethod
    def assess(self, rgba: np.ndarray, context: DetectorContext) -> Critique:
        """Judge an ``(H, W, 4)`` RGBA sprite against ``context.subject``."""
