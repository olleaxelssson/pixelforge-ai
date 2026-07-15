"""Backend registry and auto-selection."""

from __future__ import annotations

import logging

from pixelforge.core.errors import UnknownRegistryKeyError
from pixelforge.generation.backends.base import GenerationBackend
from pixelforge.generation.backends.flux import FluxSchnellBackend
from pixelforge.generation.backends.mock import MockBackend

logger = logging.getLogger("pixelforge.backends")

_BACKENDS: dict[str, GenerationBackend] = {}


def _ensure_registered() -> None:
    if not _BACKENDS:
        for backend in (FluxSchnellBackend(), MockBackend()):
            _BACKENDS[backend.name] = backend


def register_backend(backend: GenerationBackend) -> None:
    _ensure_registered()
    _BACKENDS[backend.name] = backend


def get_backend(name: str) -> GenerationBackend:
    """Resolve a backend by name; ``auto`` prefers the best available."""
    _ensure_registered()
    if name == "auto":
        flux = _BACKENDS["flux-schnell"]
        if flux.is_available():
            return flux
        logger.warning("ML dependencies unavailable; falling back to mock backend")
        return _BACKENDS["mock"]
    backend = _BACKENDS.get(name)
    if backend is None:
        raise UnknownRegistryKeyError(f"unknown generation backend: {name}")
    return backend


def list_backends() -> list[dict[str, object]]:
    _ensure_registered()
    return [{"name": b.name, "available": b.is_available()} for b in _BACKENDS.values()]
