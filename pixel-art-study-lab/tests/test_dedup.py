"""Duplicate and near-duplicate detection (the copyright/over-collection guard)."""

from __future__ import annotations

import io

import numpy as np
from PIL import Image

from studylab.config import Settings
from studylab.db import Database
from studylab.importer import ImportRequest, import_bytes

from .conftest import sprite_png, to_png


def _import(db: Database, settings: Settings, source: int, data: bytes) -> int:
    res = import_bytes(db, settings, data, ImportRequest(source_id=source, license="self"))
    return res.asset_id or 0


def test_perceptual_near_duplicate_warns(
    db: Database, settings: Settings, local_source: int
) -> None:
    # Re-encode the same sprite as a slightly different file (JPEG round-trip) → same look,
    # different bytes → should be flagged as a perceptual near-duplicate, not an exact dup.
    _import(db, settings, local_source, sprite_png(100))

    img = Image.open(io.BytesIO(sprite_png(100))).convert("RGB")
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=92)
    res = import_bytes(
        db, settings, buf.getvalue(), ImportRequest(source_id=local_source, license="self")
    )
    assert res.status == "imported"  # not byte-identical
    kinds = {w["kind"] for w in res.warnings}
    assert "perceptual" in kinds or "semantic" in kinds


def test_distinct_images_do_not_warn(
    db: Database, settings: Settings, local_source: int
) -> None:
    _import(db, settings, local_source, sprite_png(1))
    # A very different flat image should not trip near-duplicate warnings.
    arr = np.zeros((16, 16, 4), np.uint8)
    arr[..., 0] = 250
    arr[..., 3] = 255
    res = import_bytes(
        db, settings, to_png(arr), ImportRequest(source_id=local_source, license="self")
    )
    assert res.status == "imported"
    assert not res.warnings


def test_semantic_duplicate_of_identical_look(
    db: Database, settings: Settings, local_source: int
) -> None:
    # Same sprite scaled differently: bytes differ, embedding is near-identical → warned.
    _import(db, settings, local_source, sprite_png(7, scale=6))
    res = import_bytes(
        db, settings, sprite_png(7, scale=8), ImportRequest(source_id=local_source, license="self")
    )
    assert res.status == "imported"
    assert res.warnings  # some near-duplicate signal fired
