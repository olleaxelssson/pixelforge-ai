"""Search (text/colour/similar) and the local kNN tagger."""

from __future__ import annotations

from studylab.config import Settings
from studylab.db import Database
from studylab.importer import ImportRequest, import_bytes
from studylab.search import Query, search, search_by_color, search_like_asset, search_text
from studylab.tagger import TagModel

from .conftest import sprite_png, to_png
import numpy as np


def _import(db: Database, settings: Settings, source: int, data: bytes, **kw: object) -> int:
    kw.setdefault("license", "self")
    res = import_bytes(db, settings, data, ImportRequest(source_id=source, **kw))  # type: ignore[arg-type]
    return res.asset_id or 0


def test_text_search_matches_tag(db: Database, settings: Settings, local_source: int) -> None:
    aid = _import(db, settings, local_source, sprite_png(1), title="brave hero", tags=["knight"])
    assert aid in search_text(db, "knight")
    assert aid in search_text(db, "hero")


def test_color_search_ranks_by_colour(db: Database, settings: Settings, local_source: int) -> None:
    red = np.zeros((16, 16, 4), np.uint8); red[..., 0] = 240; red[..., 3] = 255
    blue = np.zeros((16, 16, 4), np.uint8); blue[..., 2] = 240; blue[..., 3] = 255
    red_id = _import(db, settings, local_source, to_png(red))
    _import(db, settings, local_source, to_png(blue))
    ranked = search_by_color(db, (255, 0, 0))
    assert ranked and ranked[0].asset_id == red_id


def test_similar_finds_same_sprite(db: Database, settings: Settings, local_source: int) -> None:
    a = _import(db, settings, local_source, sprite_png(5, scale=6))
    b = _import(db, settings, local_source, sprite_png(5, scale=8))  # same look, different bytes
    _import(db, settings, local_source, sprite_png(999))
    hits = search_like_asset(db, a)
    assert hits and hits[0].asset_id == b


def test_combined_query_filters_by_license(
    db: Database, settings: Settings, local_source: int
) -> None:
    _import(db, settings, local_source, sprite_png(1), title="a")
    cc0_src = db.upsert_source(name="cc0", kind="local", added_at="2026-01-01T00:00:00")
    _import(db, settings, cc0_src, sprite_png(2), license="CC0-1.0")  # type: ignore[arg-type]
    res = search(db, Query(text=None, license="CC0-1.0"))
    ids = {r.asset_id for r in res}
    for aid in ids:
        assert db.get_asset(aid)["license"] == "CC0-1.0"


def test_tagger_learns_and_suggests(db: Database, settings: Settings, local_source: int) -> None:
    # Two labelled examples; a query near one of them should inherit its tag.
    _import(db, settings, local_source, sprite_png(10), tags=["hero"])
    _import(db, settings, local_source, sprite_png(11), tags=["hero"])
    model = TagModel.fit(db)
    assert model.size == 2

    from studylab.analysis import analyze
    from PIL import Image
    import io

    img = Image.open(io.BytesIO(sprite_png(10))); img.load()
    emb = analyze(img).embedding
    suggestions = model.suggest(emb, threshold=0.1)
    assert any(s.tag == "hero" for s in suggestions)


def test_tagger_excludes_auto_tags(db: Database, settings: Settings, local_source: int) -> None:
    aid = _import(db, settings, local_source, sprite_png(20))
    # Give it ONLY auto tags → tagger must not train on it.
    db.add_tags(aid, ["autoish"], origin="auto")
    model = TagModel.fit(db)
    assert model.size == 0


def test_tagger_roundtrips_to_disk(
    db: Database, settings: Settings, local_source: int, tmp_path
) -> None:
    _import(db, settings, local_source, sprite_png(30), tags=["a", "b"])
    model = TagModel.fit(db)
    path = tmp_path / "m.npz"
    model.save(path)
    loaded = TagModel.load(path)
    assert loaded.size == model.size
    assert loaded.tag_sets == model.tag_sets
