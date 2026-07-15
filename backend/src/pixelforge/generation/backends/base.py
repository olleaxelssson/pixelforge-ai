"""GenerationBackend interface: Stage A (diffusion) abstraction."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field

from PIL import Image

ProgressFn = Callable[[float], None]


@dataclass
class DiffusionSpec:
    """Everything a Stage A backend needs to produce candidate images."""

    prompt: str
    negative_prompt: str = ""
    resolution: int = 1024
    steps: int = 4
    seed: int = 0
    batch_size: int = 1
    reference_image: Image.Image | None = None
    reference_strength: float = 0.6
    extra: dict[str, object] = field(default_factory=dict)


class GenerationBackend(ABC):
    name: str = "abstract"

    @abstractmethod
    def is_available(self) -> bool:
        """Whether this backend can run on the current machine/installation."""

    @abstractmethod
    def generate(self, spec: DiffusionSpec, on_progress: ProgressFn) -> list[Image.Image]:
        """Produce ``spec.batch_size`` RGB(A) images at ``spec.resolution``."""
