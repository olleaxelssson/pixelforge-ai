"""Palette import/export: JSON (native), JASC-PAL, and GIMP GPL formats."""

from __future__ import annotations

import json
from pathlib import Path

from pixelforge.core.errors import InvalidPaletteError
from pixelforge.palettes.model import Palette, hex_to_rgb, rgb_to_hex


def load_palette_file(path: Path) -> Palette:
    suffix = path.suffix.lower()
    if suffix == ".json":
        return _load_json(path)
    if suffix == ".pal":
        return _load_jasc(path)
    if suffix == ".gpl":
        return _load_gpl(path)
    raise InvalidPaletteError(f"unsupported palette format: {path.name}")


def save_palette_file(palette: Palette, path: Path) -> None:
    suffix = path.suffix.lower()
    if suffix == ".json":
        path.write_text(palette.model_dump_json(indent=2))
    elif suffix == ".pal":
        lines = ["JASC-PAL", "0100", str(len(palette.colors))]
        lines += ["{} {} {}".format(*hex_to_rgb(c)) for c in palette.colors]
        path.write_text("\n".join(lines) + "\n")
    elif suffix == ".gpl":
        lines = ["GIMP Palette", f"Name: {palette.name}", "#"]
        lines += ["{:3d} {:3d} {:3d}\tcolor".format(*hex_to_rgb(c)) for c in palette.colors]
        path.write_text("\n".join(lines) + "\n")
    else:
        raise InvalidPaletteError(f"unsupported palette format: {path.name}")


def _load_json(path: Path) -> Palette:
    try:
        data = json.loads(path.read_text())
        return Palette(
            id=data.get("id", path.stem),
            name=data.get("name", path.stem),
            colors=data["colors"],
        )
    except (json.JSONDecodeError, KeyError, ValueError) as exc:
        raise InvalidPaletteError(f"{path.name}: {exc}") from exc


def _load_jasc(path: Path) -> Palette:
    lines = [line.strip() for line in path.read_text().splitlines() if line.strip()]
    if len(lines) < 3 or lines[0] != "JASC-PAL":
        raise InvalidPaletteError(f"{path.name}: not a JASC-PAL file")
    colors = []
    for line in lines[3:]:
        parts = line.split()
        if len(parts) < 3:
            raise InvalidPaletteError(f"{path.name}: bad color line: {line}")
        r, g, b = (int(p) for p in parts[:3])
        colors.append(rgb_to_hex((r, g, b)))
    return Palette(id=path.stem, name=path.stem, colors=colors)


def _load_gpl(path: Path) -> Palette:
    name = path.stem
    colors = []
    for line in path.read_text().splitlines():
        stripped = line.strip()
        if stripped.startswith("Name:"):
            name = stripped[5:].strip()
            continue
        if not stripped or stripped.startswith(("#", "GIMP")):
            continue
        parts = stripped.split()
        if len(parts) >= 3 and all(p.isdigit() for p in parts[:3]):
            r, g, b = (int(p) for p in parts[:3])
            colors.append(rgb_to_hex((r, g, b)))
    if not colors:
        raise InvalidPaletteError(f"{path.name}: no colors found")
    return Palette(id=path.stem, name=name, colors=colors)
