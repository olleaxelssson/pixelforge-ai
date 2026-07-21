"""Critic-backend registry and auto-selection (D-013)."""

from __future__ import annotations

import logging

from pixelforge.core.errors import UnknownRegistryKeyError
from pixelforge.qa.critic_backends.base import CriticBackend
from pixelforge.qa.critic_backends.mock import MockCriticBackend
from pixelforge.qa.critic_backends.vlm import VLMCriticBackend

logger = logging.getLogger("pixelforge.critic")

_BACKENDS: dict[str, CriticBackend] = {}


def _ensure_registered() -> None:
    if not _BACKENDS:
        for backend in (VLMCriticBackend(), MockCriticBackend()):
            _BACKENDS[backend.name] = backend


def register_critic_backend(backend: CriticBackend) -> None:
    """Register a plugin critic backend (D-014)."""
    _ensure_registered()
    _BACKENDS[backend.name] = backend


def get_critic_backend(name: str) -> CriticBackend:
    """Resolve a critic backend by name; ``auto`` prefers the best available (VLM → mock)."""
    _ensure_registered()
    if name in ("auto", ""):
        vlm = _BACKENDS["vlm"]
        if vlm.is_available():
            return vlm
        logger.info("VLM critic unavailable; using the deterministic mock critic backend")
        return _BACKENDS["mock"]
    backend = _BACKENDS.get(name)
    if backend is None:
        raise UnknownRegistryKeyError(f"unknown critic backend: {name}")
    return backend
