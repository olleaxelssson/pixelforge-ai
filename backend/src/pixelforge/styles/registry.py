"""Style presets: data-driven artistic styles for the generation pipeline.

Each style contributes prompt fragments and optional pipeline overrides
(e.g. a default palette). Users can add styles by dropping TOML files in the
user styles directory; see ``presets_builtin.py`` for the shape.
"""

from __future__ import annotations

import sys
from pathlib import Path

from pixelforge.core.errors import UnknownRegistryKeyError
from pixelforge.styles.model import StylePreset
from pixelforge.styles.presets_builtin import BUILTIN_STYLES

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


class StyleRegistry:
    def __init__(self, user_dir: Path | None = None) -> None:
        self._styles: dict[str, StylePreset] = {s.id: s for s in BUILTIN_STYLES}
        if user_dir is not None and user_dir.exists():
            for path in sorted(user_dir.glob("*.toml")):
                data = tomllib.loads(path.read_text())
                style = StylePreset(
                    id=data.get("id", path.stem), **{k: v for k, v in data.items() if k != "id"}
                )
                self._styles[style.id] = style

    def list(self) -> list[StylePreset]:
        return list(self._styles.values())

    def get(self, style_id: str) -> StylePreset:
        style = self._styles.get(style_id)
        if style is None:
            raise UnknownRegistryKeyError(f"unknown style: {style_id}")
        return style
