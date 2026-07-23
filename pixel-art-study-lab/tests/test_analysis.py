"""Analysis: palette, pixel-art detection, embeddings, digest, sheets/GIFs, notes, critique."""

from __future__ import annotations

import io

import numpy as np
from PIL import Image

from studylab.analysis import analyze
from studylab.analysis.critique import critique
from studylab.analysis.embed import EMBED_DIM, cosine, embed
from studylab.analysis.llm_digest import VERSION, build_digest
from studylab.analysis.palette import analyze_palette
from studylab.analysis.pixelart import analyze_pixelart

from .conftest import noise_png, sprite_png, strip_png, gif_bytes


def _open(data: bytes) -> Image.Image:
    img = Image.open(io.BytesIO(data))
    img.load()
    return img


def test_palette_counts_and_ramps() -> None:
    arr = np.zeros((8, 8, 4), np.uint8)
    arr[:4, :, :3] = (200, 40, 40)
    arr[4:, :, :3] = (40, 40, 200)
    arr[..., 3] = 255
    pal = analyze_palette(arr)
    assert pal.color_count == 2
    assert pal.hex  # dominant hex list present


def test_pixel_art_detected_and_noise_rejected() -> None:
    sprite = analyze(_open(sprite_png())).columns
    assert sprite["is_pixel_art"] == 1
    assert sprite["pixel_art_confidence"] >= 0.55

    noise = analyze(_open(noise_png())).columns
    assert noise["is_pixel_art"] == 0


def test_grid_scale_recovered() -> None:
    # A 16×16 sprite upscaled ×6 should report a grid scale of 6.
    res = analyze(_open(sprite_png(scale=6)))
    assert res.columns["grid_scale"] == 6


def test_embedding_is_deterministic_and_normalised() -> None:
    arr = np.asarray(_open(sprite_png()).convert("RGBA"), np.uint8)
    a, b = embed(arr), embed(arr)
    assert a.shape == (EMBED_DIM,)
    assert np.allclose(a, b)  # deterministic
    assert abs(np.linalg.norm(a) - 1.0) < 1e-5  # L2-normalised
    assert abs(cosine(a, a) - 1.0) < 1e-5


def test_embedding_similar_beats_dissimilar() -> None:
    s1 = embed(np.asarray(_open(sprite_png(100)).convert("RGBA"), np.uint8))
    s2 = embed(np.asarray(_open(sprite_png(100)).convert("RGBA"), np.uint8))
    other = embed(np.asarray(_open(noise_png()).convert("RGBA"), np.uint8))
    assert cosine(s1, s2) > cosine(s1, other)


def test_digest_format_is_stable_and_parseable() -> None:
    res = analyze(_open(sprite_png()))
    digest = build_digest(res.analysis, {"license": "CC0-1.0", "tags": ["hero"]})
    assert digest.startswith(VERSION)
    assert "grid=" in digest and "pal=" in digest
    assert "license=CC0-1.0" in digest
    assert "hero" in digest


def test_spritesheet_layout_detected() -> None:
    res = analyze(_open(strip_png()))
    frames = res.analysis["frames"]
    assert frames["is_sheet"] or frames["columns"] >= 2


def test_gif_frames_counted() -> None:
    res = analyze(_open(gif_bytes()))
    assert res.columns["frame_count"] >= 2
    assert res.analysis["frames"]["is_animation"]


def test_notes_and_critique_present() -> None:
    res = analyze(_open(sprite_png()))
    assert res.analysis["notes"]["notes"]
    crit = critique(res.analysis)
    assert "strengths" in crit and "suggestions" in crit
