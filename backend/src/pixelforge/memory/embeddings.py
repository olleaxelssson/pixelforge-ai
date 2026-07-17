"""Identity embeddings behind a swappable interface (D-011).

M10 ships the deterministic ``MockEmbeddingBackend`` — a downscaled RGBA feature, L2-normalized —
which is enough to *measure* identity similarity in CI with no weights. A CLIP/SigLIP backend
implements the same interface in a later milestone; the drift gate and store never change.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable

import numpy as np
from PIL import Image

from pixelforge.core.errors import UnknownRegistryKeyError

_GRID = 12


class EmbeddingBackend(ABC):
    name: str = "abstract"

    @abstractmethod
    def is_available(self) -> bool:
        """Whether this backend can run on the current machine/installation."""

    @abstractmethod
    def embed(self, image: Image.Image) -> list[float]:
        """Return an L2-normalized identity embedding for an image."""


class MockEmbeddingBackend(EmbeddingBackend):
    name = "mock"

    def is_available(self) -> bool:
        return True

    def embed(self, image: Image.Image) -> list[float]:
        small = image.convert("RGBA").resize((_GRID, _GRID), Image.Resampling.NEAREST)
        vector = np.asarray(small, dtype=np.float64).flatten() / 255.0
        norm = float(np.linalg.norm(vector))
        if norm == 0.0:
            return vector.tolist()  # fully-transparent/black sprite → zero vector
        return (vector / norm).tolist()


_BACKENDS: dict[str, Callable[[], EmbeddingBackend]] = {
    "mock": MockEmbeddingBackend,
}


def get_embedding_backend(name: str) -> EmbeddingBackend:
    if name in ("auto", ""):
        name = "mock"
    factory = _BACKENDS.get(name)
    if factory is None:
        raise UnknownRegistryKeyError(f"unknown embedding backend: {name}")
    return factory()


def list_embedding_backends() -> list[dict[str, object]]:
    return [
        {"id": key, "available": factory().is_available()} for key, factory in _BACKENDS.items()
    ]
