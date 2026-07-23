"""Search over the library: by text, by example image, by colour/palette, by dimensions and tags.

Everything runs locally against SQLite plus the on-disk vector index (float32 embeddings + a numpy
cosine scan). For a personal-scale library (thousands of assets) a linear scan is instant and keeps
the whole thing dependency-free; there is no ANN index to build or keep in sync.

* :func:`search_text` — FTS5 over titles, creators, source names, tags and study notes.
* :func:`search_similar` — cosine kNN over embeddings, for "more like this asset".
* :func:`search_by_color` — nearest dominant colour (CIE-ish weighted RGB) to a target.
* :func:`search` — a combined query object that AND-composes any of the above with metadata filters.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from studylab.analysis.embed import embed
from studylab.db import Database


@dataclass
class ScoredAsset:
    asset_id: int
    score: float  # higher is better/closer (1.0 for pure filter matches)


def search_text(db: Database, query: str, limit: int = 60) -> list[int]:
    """Full-text search; returns asset ids in FTS rank order."""
    query = query.strip()
    if not query:
        return []
    return db.search_fts(query, limit)


def search_similar(
    db: Database, embedding: np.ndarray, *, limit: int = 24, exclude_id: int | None = None
) -> list[ScoredAsset]:
    """Cosine-nearest assets to a query embedding (both sides L2-normalised)."""
    scored: list[ScoredAsset] = []
    for asset_id, blob, dim in db.all_embeddings():
        if asset_id == exclude_id or dim != embedding.shape[0]:
            continue
        other = np.frombuffer(blob, dtype=np.float32)
        scored.append(ScoredAsset(asset_id, float(np.dot(embedding, other))))
    scored.sort(key=lambda s: s.score, reverse=True)
    return scored[:limit]


def search_like_asset(db: Database, asset_id: int, *, limit: int = 24) -> list[ScoredAsset]:
    """'More like this': use a stored asset's own embedding as the query."""
    asset = db.get_asset(asset_id)
    if not asset or not asset.get("embedding"):
        return []
    emb = np.frombuffer(asset["embedding"], dtype=np.float32)
    return search_similar(db, emb, limit=limit, exclude_id=asset_id)


def _color_distance(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    """Perceptually-weighted RGB distance (cheap approximation of Lab ΔE)."""
    rmean = (a[0] + b[0]) / 2.0
    dr, dg, db_ = a[0] - b[0], a[1] - b[1], a[2] - b[2]
    return float(
        ((2 + rmean / 256) * dr * dr + 4 * dg * dg + (2 + (255 - rmean) / 256) * db_ * db_) ** 0.5
    )


def search_by_color(
    db: Database, target: tuple[int, int, int], *, limit: int = 24
) -> list[ScoredAsset]:
    """Assets whose closest dominant colour is nearest ``target``. Score = 1/(1+distance)."""
    best: dict[int, float] = {}
    for asset_id, r, g, b in db.color_index():
        dist = _color_distance(target, (r, g, b))
        if asset_id not in best or dist < best[asset_id]:
            best[asset_id] = dist
    scored = [ScoredAsset(aid, 1.0 / (1.0 + dist)) for aid, dist in best.items()]
    scored.sort(key=lambda s: s.score, reverse=True)
    return scored[:limit]


@dataclass
class Query:
    text: str | None = None
    color: tuple[int, int, int] | None = None
    like_image: np.ndarray | None = None  # an RGBA array to embed and match
    like_asset_id: int | None = None
    tag: str | None = None
    license: str | None = None
    pixel_art_only: bool = False
    min_w: int | None = None
    max_w: int | None = None
    limit: int = 60


def _metadata_ids(db: Database, q: Query) -> set[int] | None:
    """Ids passing the metadata filters, or None if no metadata filter is set."""
    if not (q.tag or q.license or q.pixel_art_only or q.min_w is not None or q.max_w is not None):
        return None
    rows = db.list_assets(
        limit=100_000,
        pixel_art_only=q.pixel_art_only,
        license=q.license,
        tag=q.tag,
        min_w=q.min_w,
        max_w=q.max_w,
    )
    return {int(r["id"]) for r in rows}


def search(db: Database, q: Query) -> list[ScoredAsset]:
    """Compose the query: rank by the strongest similarity signal, AND-filtered by metadata.

    Ranking signals are considered in priority order (example image > example asset > colour > text).
    Whichever is present provides the score; metadata filters only narrow the candidate set. With no
    similarity signal at all, results are the most-recent assets that pass the filters.
    """
    allowed = _metadata_ids(db, q)

    ranked: list[ScoredAsset]
    if q.like_image is not None:
        ranked = search_similar(db, embed(q.like_image), limit=q.limit * 4)
    elif q.like_asset_id is not None:
        ranked = search_like_asset(db, q.like_asset_id, limit=q.limit * 4)
    elif q.color is not None:
        ranked = search_by_color(db, q.color, limit=q.limit * 4)
    elif q.text:
        ranked = [ScoredAsset(aid, 1.0) for aid in search_text(db, q.text, q.limit * 4)]
    else:
        rows = db.list_assets(
            limit=q.limit,
            pixel_art_only=q.pixel_art_only,
            license=q.license,
            tag=q.tag,
            min_w=q.min_w,
            max_w=q.max_w,
        )
        return [ScoredAsset(int(r["id"]), 1.0) for r in rows]

    if allowed is not None:
        ranked = [s for s in ranked if s.asset_id in allowed]
    return ranked[: q.limit]
