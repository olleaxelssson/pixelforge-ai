"""A tiny, legally-safe demo dataset — procedurally generated here, so it is CC0 by construction.

No network, no third-party art. Produces a handful of sprites, two seamless textures, a sprite-sheet
strip, and an animated GIF, so every part of the pipeline (analysis, dedup, sheets, animation) has
something to chew on out of the box.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

_PALETTE = [
    (26, 28, 44), (93, 39, 93), (177, 62, 83), (239, 125, 87), (255, 205, 117),
    (167, 240, 112), (56, 183, 100), (37, 113, 121), (41, 173, 246), (244, 244, 244),
]
CREATOR = "PixelArtStudyLab demo generator"
LICENSE = "CC0-1.0"


def _luma(c: tuple[int, int, int]) -> float:
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def _sprite(seed: int, size: int = 16) -> np.ndarray:
    rng = np.random.default_rng(seed)
    half = (size + 1) // 2
    grid = np.zeros((size, size), np.int8)
    for y in range(size):
        for x in range(half):
            dx, dy = x / (size - 1) - 0.5, y / (size - 1) - 0.5
            dist = (dx * dx * 1.15 + dy * dy) ** 0.5
            grid[y, x] = 1 if rng.random() < 0.62 - dist * 0.95 else 0
    for _ in range(3):
        ng = grid.copy()
        for y in range(size):
            for x in range(half):
                if x == 0 or y in (0, size - 1):
                    ng[y, x] = 0
                    continue
                n = int(grid[max(y - 1, 0) : y + 2, max(x - 1, 0) : x + 2].sum())
                ng[y, x] = 1 if n >= 5 else 0 if n <= 2 else grid[y, x]
        grid = ng
    for y in range(size):
        for x in range(half):
            grid[y, size - 1 - x] = grid[y, x]

    ramp = sorted(_PALETTE, key=_luma)
    dark = ramp[0]
    out = np.zeros((size, size, 4), np.uint8)
    for y in range(size):
        for x in range(size):
            if grid[y, x]:
                light = 1 - ((x / (size - 1)) + (y / (size - 1))) / 2
                idx = min(len(ramp) - 1, max(1, round(light * (len(ramp) - 2)) + 1))
                out[y, x] = (*ramp[idx], 255)
            else:
                nb = grid[max(y - 1, 0) : y + 2, max(x - 1, 0) : x + 2].sum()
                if nb > 0:
                    out[y, x] = (*dark, 255)
    return out


def _texture(seed: int, size: int = 32) -> np.ndarray:
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, 6, (size, size))
    rgb = np.array(_PALETTE[:6], np.float64)[idx]
    # Wrap-blend the edges so it tiles seamlessly.
    band = size // 4
    for i in range(band):
        w = 0.5 * (1 - i / band)
        rgb[:, i], rgb[:, -1 - i] = (
            (1 - w) * rgb[:, i] + w * rgb[:, -1 - i],
            (1 - w) * rgb[:, -1 - i] + w * rgb[:, i],
        )
        rgb[i, :], rgb[-1 - i, :] = (
            (1 - w) * rgb[i, :] + w * rgb[-1 - i, :],
            (1 - w) * rgb[-1 - i, :] + w * rgb[i, :],
        )
    out = np.zeros((size, size, 4), np.uint8)
    out[..., :3] = np.rint(rgb).astype(np.uint8)
    out[..., 3] = 255
    return out


def generate_demo(out_dir: Path, scale: int = 6) -> list[Path]:
    """Write the demo dataset to ``out_dir`` (upscaled ×``scale`` for visibility). Returns paths."""
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []

    def save(arr: np.ndarray, name: str) -> None:
        img = Image.fromarray(arr, "RGBA").resize(
            (arr.shape[1] * scale, arr.shape[0] * scale), Image.Resampling.NEAREST
        )
        p = out_dir / name
        img.save(p)
        paths.append(p)

    for i in range(8):
        save(_sprite(100 + i), f"creature_{i:02d}.png")
    save(_texture(1), "texture_grass.png")
    save(_texture(2), "texture_stone.png")

    # Sprite-sheet strip: four sprites side by side (→ detected as a 4×1 sheet).
    strip = np.concatenate([_sprite(200 + i) for i in range(4)], axis=1)
    save(strip, "spritesheet_walk.png")

    # Animated GIF: four frames of one evolving sprite.
    frames = [
        Image.fromarray(_sprite(300 + i), "RGBA").resize((16 * scale, 16 * scale), Image.Resampling.NEAREST)
        for i in range(4)
    ]
    gif_path = out_dir / "anim_blink.gif"
    frames[0].save(gif_path, save_all=True, append_images=frames[1:], duration=150, loop=0, disposal=2)
    paths.append(gif_path)

    return paths
