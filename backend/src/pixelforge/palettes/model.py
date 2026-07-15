"""Palette domain model."""

from __future__ import annotations

from pydantic import BaseModel, field_validator

RGB = tuple[int, int, int]


class Palette(BaseModel):
    id: str
    name: str
    colors: list[str]  # "#rrggbb" strings
    builtin: bool = False

    @field_validator("colors")
    @classmethod
    def _validate_colors(cls, colors: list[str]) -> list[str]:
        normalized = []
        for color in colors:
            value = color.lower().lstrip("#")
            if len(value) != 6 or any(c not in "0123456789abcdef" for c in value):
                raise ValueError(f"invalid hex color: {color}")
            normalized.append(f"#{value}")
        return normalized

    def as_rgb(self) -> list[RGB]:
        return [hex_to_rgb(color) for color in self.colors]


def hex_to_rgb(color: str) -> RGB:
    value = color.lstrip("#")
    return (int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16))


def rgb_to_hex(rgb: RGB) -> str:
    return "#{:02x}{:02x}{:02x}".format(*rgb)
