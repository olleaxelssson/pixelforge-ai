"""Generation modes: what kind of asset is being generated.

A mode contributes a prompt template and sensible defaults (size, whether the
background should be transparent). ``{prompt}`` in the template is replaced by
the user's prompt text.
"""

from __future__ import annotations

from pydantic import BaseModel

from pixelforge.core.errors import UnknownRegistryKeyError


class GenerationMode(BaseModel):
    id: str
    name: str
    description: str = ""
    prompt_template: str = "{prompt}"
    default_width: int = 32
    default_height: int = 32
    transparent_background: bool = True
    accepts_reference_image: bool = False


BUILTIN_MODES: list[GenerationMode] = [
    GenerationMode(
        id="text-to-pixel",
        name="Text → Pixel Art",
        description="Free-form pixel art from a text prompt.",
        prompt_template="{prompt}",
    ),
    GenerationMode(
        id="image-to-pixel",
        name="Image → Pixel Art",
        description="Convert a reference image into pixel art.",
        prompt_template="pixel art rendition of the reference image, {prompt}",
        accepts_reference_image=True,
        transparent_background=False,
    ),
    GenerationMode(
        id="sketch-to-pixel",
        name="Sketch → Pixel Art",
        description="Turn a rough sketch into finished pixel art.",
        prompt_template="finished pixel art following the sketch composition, {prompt}",
        accepts_reference_image=True,
    ),
    GenerationMode(
        id="character",
        name="Character Generator",
        description="Game character sprites.",
        prompt_template=(
            "full-body game character sprite of {prompt}, centered, neutral standing pose"
        ),
    ),
    GenerationMode(
        id="creature",
        name="Creature Generator",
        description="Monsters and creatures.",
        prompt_template="game creature sprite of {prompt}, full body, menacing readable silhouette",
    ),
    GenerationMode(
        id="environment",
        name="Environment Generator",
        description="Scenes and environment art.",
        prompt_template="game environment scene of {prompt}, layered composition",
        default_width=128,
        default_height=128,
        transparent_background=False,
    ),
    GenerationMode(
        id="item",
        name="Item Generator",
        description="Inventory items and pickups.",
        prompt_template="game item icon of {prompt}, centered on transparent background",
        default_width=24,
        default_height=24,
    ),
    GenerationMode(
        id="weapon",
        name="Weapon Generator",
        description="Weapons at icon or sprite scale.",
        prompt_template="game weapon sprite of {prompt}, diagonal composition, centered",
    ),
    GenerationMode(
        id="armor",
        name="Armor Generator",
        description="Armor pieces and equipment.",
        prompt_template="game armor equipment sprite of {prompt}, centered, front view",
    ),
    GenerationMode(
        id="portrait",
        name="Portrait Generator",
        description="Character portraits for dialogue boxes.",
        prompt_template="pixel art portrait of {prompt}, head and shoulders, expressive face",
        default_width=64,
        default_height=64,
        transparent_background=False,
    ),
    GenerationMode(
        id="icon",
        name="Icon Generator",
        description="UI and skill icons.",
        prompt_template="game skill icon of {prompt}, bold central symbol, high contrast",
        default_width=16,
        default_height=16,
    ),
    GenerationMode(
        id="tileset",
        name="Tileset Generator",
        description="Seamless terrain tiles.",
        prompt_template="seamless tileable game texture tile of {prompt}, edge-to-edge continuity",
        transparent_background=False,
    ),
    GenerationMode(
        id="background",
        name="Background Generator",
        description="Parallax-ready backgrounds.",
        prompt_template="game background of {prompt}, wide composition, parallax-friendly layers",
        default_width=256,
        default_height=128,
        transparent_background=False,
    ),
    GenerationMode(
        id="ui-element",
        name="UI Element Generator",
        description="Buttons, frames, bars, panels.",
        prompt_template="game UI element, {prompt}, clean geometric pixel design",
        default_width=48,
        default_height=16,
    ),
    GenerationMode(
        id="sprite-sheet",
        name="Sprite Sheet Generator",
        description="Multi-frame animation sheets.",
        prompt_template="game character sprite for animation, {prompt}, consistent proportions",
    ),
]


class ModeRegistry:
    def __init__(self) -> None:
        self._modes: dict[str, GenerationMode] = {m.id: m for m in BUILTIN_MODES}

    def list(self) -> list[GenerationMode]:
        return list(self._modes.values())

    def get(self, mode_id: str) -> GenerationMode:
        mode = self._modes.get(mode_id)
        if mode is None:
            raise UnknownRegistryKeyError(f"unknown mode: {mode_id}")
        return mode
