"""Palette service: registry of builtin + user palettes with import/export."""

from __future__ import annotations

from pathlib import Path

from pixelforge.core.errors import UnknownRegistryKeyError
from pixelforge.palettes.io import load_palette_file, save_palette_file
from pixelforge.palettes.model import Palette
from pixelforge.palettes.presets import BUILTIN_PALETTES


class PaletteService:
    def __init__(self, user_dir: Path) -> None:
        self._user_dir = user_dir
        self._palettes: dict[str, Palette] = {p.id: p for p in BUILTIN_PALETTES}
        self._load_user_palettes()

    def _load_user_palettes(self) -> None:
        if not self._user_dir.exists():
            return
        for path in sorted(self._user_dir.iterdir()):
            if path.suffix.lower() in (".json", ".pal", ".gpl"):
                palette = load_palette_file(path)
                self._palettes[palette.id] = palette

    def list(self) -> list[Palette]:
        return list(self._palettes.values())

    def get(self, palette_id: str) -> Palette:
        palette = self._palettes.get(palette_id)
        if palette is None:
            raise UnknownRegistryKeyError(f"unknown palette: {palette_id}")
        return palette

    def save(self, palette: Palette) -> Palette:
        self._palettes[palette.id] = palette
        save_palette_file(palette, self._user_dir / f"{palette.id}.json")
        return palette

    def delete(self, palette_id: str) -> None:
        palette = self.get(palette_id)
        if palette.builtin:
            raise UnknownRegistryKeyError("builtin palettes cannot be deleted")
        del self._palettes[palette_id]
        for suffix in (".json", ".pal", ".gpl"):
            candidate = self._user_dir / f"{palette_id}{suffix}"
            if candidate.exists():
                candidate.unlink()
