"""Shared fixtures and image helpers. Everything runs against a throwaway data directory, so tests
never touch a real library and never hit the network."""

from __future__ import annotations

import io
from collections.abc import Iterator
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from studylab.config import Settings
from studylab.db import Database, open_db
from studylab.demo import _sprite, _texture


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    s = Settings(data_dir=tmp_path / "data", vlm_api_key=None, vlm_provider="local", user_agent="test")
    s.ensure_dirs()
    return s


@pytest.fixture
def db(settings: Settings) -> Iterator[Database]:
    conn = open_db(settings.db_path)
    yield conn
    conn.close()


@pytest.fixture
def local_source(db: Database) -> int:
    return db.upsert_source(name="local", kind="local", added_at="2026-01-01T00:00:00")


def to_png(arr: np.ndarray, scale: int = 6) -> bytes:
    img = Image.fromarray(arr, "RGBA").resize(
        (arr.shape[1] * scale, arr.shape[0] * scale), Image.Resampling.NEAREST
    )
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def sprite_png(seed: int = 100, scale: int = 6) -> bytes:
    """A clean, low-palette pixel-art sprite (passes the is-pixel-art heuristic)."""
    return to_png(_sprite(seed), scale)


def texture_png(seed: int = 1, scale: int = 6) -> bytes:
    return to_png(_texture(seed), scale)


def noise_png(seed: int = 0, size: int = 128) -> bytes:
    """A high-resolution noise image (deliberately *not* pixel art)."""
    rng = np.random.default_rng(seed)
    arr = rng.integers(0, 256, (size, size, 4), dtype=np.uint8)
    arr[..., 3] = 255
    buf = io.BytesIO()
    Image.fromarray(arr, "RGBA").save(buf, "PNG")
    return buf.getvalue()


def strip_png(seeds: tuple[int, ...] = (200, 201, 202, 203), scale: int = 6) -> bytes:
    """A horizontal sprite-sheet strip (N frames side by side)."""
    strip = np.concatenate([_sprite(s) for s in seeds], axis=1)
    return to_png(strip, scale)


def gif_bytes(seeds: tuple[int, ...] = (300, 301, 302, 303), scale: int = 6) -> bytes:
    frames = [
        Image.fromarray(_sprite(s), "RGBA").resize((16 * scale, 16 * scale), Image.Resampling.NEAREST)
        for s in seeds
    ]
    buf = io.BytesIO()
    frames[0].save(buf, "GIF", save_all=True, append_images=frames[1:], duration=120, loop=0)
    return buf.getvalue()
