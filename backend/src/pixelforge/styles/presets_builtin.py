"""Built-in artistic style presets."""

from __future__ import annotations

from pixelforge.styles.model import StylePreset


def _styles() -> list[StylePreset]:
    common_negative = (
        "blurry, anti-aliased edges, gradients, photorealistic, 3d render, "
        "jpeg artifacts, watermark, text, signature"
    )
    return [
        StylePreset(
            id="nes-inspired",
            name="NES-inspired",
            description="8-bit era: tiny palettes, bold outlines, chunky shading.",
            prompt_prefix="8-bit pixel art,",
            prompt_suffix="limited 4-color-per-sprite palette, bold black outline, flat shading",
            negative_prompt=common_negative,
            default_palette_id="8bit-console",
            default_max_colors=8,
            tags=["retro", "8bit"],
        ),
        StylePreset(
            id="snes-inspired",
            name="SNES-inspired",
            description="16-bit era: richer palettes, soft dithered shading.",
            prompt_prefix="16-bit pixel art,",
            prompt_suffix="rich but limited palette, careful dithering, detailed shading",
            negative_prompt=common_negative,
            default_palette_id="16bit-console",
            default_max_colors=24,
            tags=["retro", "16bit"],
        ),
        StylePreset(
            id="gameboy-inspired",
            name="Game Boy-inspired",
            description="4-shade monochrome green handheld look.",
            prompt_prefix="monochrome green pixel art,",
            prompt_suffix="four shades of green only, high contrast silhouette",
            negative_prompt=common_negative + ", color",
            default_palette_id="monochrome-handheld",
            default_max_colors=4,
            tags=["retro", "monochrome"],
        ),
        StylePreset(
            id="gba-inspired",
            name="GBA-inspired",
            description="32-bit handheld: bright saturated palettes, clean outlines.",
            prompt_prefix="32-bit handheld pixel art,",
            prompt_suffix="bright saturated colors, clean dark outline, cel shading",
            negative_prompt=common_negative,
            default_palette_id="handheld-32",
            default_max_colors=32,
            tags=["retro", "handheld"],
        ),
        StylePreset(
            id="modern-indie",
            name="Modern Indie",
            description="Contemporary indie pixel art: expressive palettes, subtle AA.",
            prompt_prefix="modern indie pixel art,",
            prompt_suffix=(
                "expressive limited palette, selective anti-aliasing, atmospheric lighting"
            ),
            negative_prompt=common_negative,
            default_max_colors=32,
            tags=["modern"],
        ),
        StylePreset(
            id="jrpg",
            name="JRPG",
            description="Classic JRPG sprite look: 3/4 top-down, friendly proportions.",
            prompt_prefix="JRPG pixel art sprite,",
            prompt_suffix="3/4 top-down perspective, chibi proportions, clean outline",
            negative_prompt=common_negative,
            default_max_colors=24,
            tags=["rpg", "topdown"],
        ),
        StylePreset(
            id="tactical-rpg",
            name="Tactical RPG",
            description="Tactics-style sprites: isometric-friendly, muted palettes.",
            prompt_prefix="tactical RPG pixel art,",
            prompt_suffix="muted earthy palette, detailed armor, battle-ready pose",
            negative_prompt=common_negative,
            default_max_colors=24,
            tags=["rpg", "tactics"],
        ),
        StylePreset(
            id="roguelike",
            name="Roguelike",
            description="Dungeon-crawler look: dark palettes, high readability.",
            prompt_prefix="roguelike dungeon pixel art,",
            prompt_suffix="dark moody palette, torch-lit, highly readable silhouette",
            negative_prompt=common_negative,
            default_max_colors=16,
            tags=["dungeon"],
        ),
        StylePreset(
            id="isometric",
            name="Isometric",
            description="Isometric projection with 2:1 pixel ratio staircase edges.",
            prompt_prefix="isometric pixel art,",
            prompt_suffix=(
                "isometric 2:1 projection, clean staircase edges, consistent light from top-left"
            ),
            negative_prompt=common_negative,
            default_max_colors=32,
            tags=["isometric"],
        ),
        StylePreset(
            id="top-down",
            name="Top-down",
            description="Straight top-down view for map tiles and overworld sprites.",
            prompt_prefix="top-down pixel art,",
            prompt_suffix="overhead view, game map style, tile-friendly composition",
            negative_prompt=common_negative,
            default_max_colors=24,
            tags=["topdown"],
        ),
        StylePreset(
            id="side-view",
            name="Side-view",
            description="Platformer side profile with strong silhouette.",
            prompt_prefix="side-view platformer pixel art,",
            prompt_suffix="side profile, strong silhouette, ground contact shadow",
            negative_prompt=common_negative,
            default_max_colors=24,
            tags=["platformer"],
        ),
        StylePreset(
            id="hand-painted",
            name="Hand-painted Pixel Art",
            description="Painterly cluster shading, no hard outlines.",
            prompt_prefix="hand-painted pixel art,",
            prompt_suffix="painterly color clusters, soft shading, no hard outline, textured",
            negative_prompt=common_negative,
            default_max_colors=48,
            outline=False,
            tags=["painterly"],
        ),
    ]


BUILTIN_STYLES = _styles()
