"""Exporter registry."""

from __future__ import annotations

from pixelforge.core.errors import UnknownRegistryKeyError
from pixelforge.exporters.aseprite import AsepriteExporter
from pixelforge.exporters.base import Exporter
from pixelforge.exporters.engines import GodotExporter, UnityExporter, UnrealExporter
from pixelforge.exporters.standard import (
    GifExporter,
    PngExporter,
    SpriteSheetExporter,
    TextureAtlasExporter,
)

_EXPORTERS: dict[str, Exporter] = {}


def _ensure_registered() -> None:
    if not _EXPORTERS:
        for exporter in (
            PngExporter(),
            GifExporter(),
            SpriteSheetExporter(),
            TextureAtlasExporter(),
            UnityExporter(),
            GodotExporter(),
            UnrealExporter(),
            AsepriteExporter(),
        ):
            _EXPORTERS[exporter.format_id] = exporter


def register_exporter(exporter: Exporter) -> None:
    _ensure_registered()
    _EXPORTERS[exporter.format_id] = exporter


def get_exporter(format_id: str) -> Exporter:
    _ensure_registered()
    exporter = _EXPORTERS.get(format_id)
    if exporter is None:
        raise UnknownRegistryKeyError(f"unknown export format: {format_id}")
    return exporter


def list_exporters() -> list[dict[str, str]]:
    _ensure_registered()
    return [{"format_id": e.format_id, "display_name": e.display_name} for e in _EXPORTERS.values()]
