"""SQLite persistence: schema, connection, and a small typed repository.

One SQLite file holds everything: sources, assets, provenance, tags, dominant colours (for
colour search), and a local vector index (embeddings stored as float32 blobs). Full-text search
uses FTS5. The design keeps *provenance first-class* — every asset row carries its source URL,
creator, license, attribution and content hash — and deletion cascades so removing a source or an
asset removes all of its records and its files.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS sources (
    id                   INTEGER PRIMARY KEY,
    name                 TEXT NOT NULL UNIQUE,
    kind                 TEXT NOT NULL,              -- 'local' | 'scraper'
    homepage             TEXT,
    terms_url            TEXT,
    license_default      TEXT,
    attribution_template TEXT,
    added_at             TEXT NOT NULL,
    notes                TEXT
);

CREATE TABLE IF NOT EXISTS assets (
    id                  INTEGER PRIMARY KEY,
    sha256              TEXT NOT NULL UNIQUE,        -- content hash (exact-dedup)
    source_id           INTEGER REFERENCES sources(id) ON DELETE CASCADE,
    title               TEXT,
    creator             TEXT,
    license             TEXT NOT NULL,
    attribution         TEXT,                        -- ready-to-display attribution string
    source_url          TEXT,                        -- provenance: where it came from
    collected_at        TEXT NOT NULL,
    file_path           TEXT NOT NULL,               -- relative to assets_dir
    thumb_path          TEXT,                        -- relative to thumbs_dir
    width               INTEGER,
    height              INTEGER,
    format              TEXT,
    frame_count         INTEGER DEFAULT 1,
    has_alpha           INTEGER DEFAULT 0,
    transparent_ratio   REAL DEFAULT 0,
    palette_size        INTEGER,
    grid_scale          INTEGER,
    is_pixel_art        INTEGER DEFAULT 0,
    pixel_art_confidence REAL DEFAULT 0,
    manual_override     INTEGER DEFAULT 0,           -- user forced is_pixel_art
    tileable_h          REAL DEFAULT 0,
    tileable_v          REAL DEFAULT 0,
    silhouette_coverage REAL DEFAULT 0,
    phash               TEXT,                         -- perceptual dHash (near-dedup)
    analysis_json       TEXT,                         -- full analysis metrics
    notes_json          TEXT,                         -- explainable study notes
    embedding           BLOB,                         -- float32 vector (local index)
    embed_dim           INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_assets_source ON assets(source_id);
CREATE INDEX IF NOT EXISTS idx_assets_phash  ON assets(phash);

CREATE TABLE IF NOT EXISTS tags (
    asset_id INTEGER NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    tag      TEXT NOT NULL,
    origin   TEXT NOT NULL DEFAULT 'user',          -- 'user' | 'auto' | 'vlm'
    UNIQUE(asset_id, tag)
);
CREATE INDEX IF NOT EXISTS idx_tags_tag ON tags(tag);

CREATE TABLE IF NOT EXISTS asset_colors (
    asset_id INTEGER NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    rank     INTEGER NOT NULL,
    r        INTEGER NOT NULL,
    g        INTEGER NOT NULL,
    b        INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_colors_asset ON asset_colors(asset_id);

-- A regular (self-contained) FTS5 index. Not contentless: we need per-row DELETE/UPDATE
-- when an asset is removed or re-indexed, which contentless tables forbid.
CREATE VIRTUAL TABLE IF NOT EXISTS assets_fts USING fts5(
    title, creator, source_name, tags, notes
);
"""


class Database:
    """A thin repository over a SQLite connection. Not thread-safe; open one per worker."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.conn = sqlite3.connect(str(path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("PRAGMA journal_mode = WAL")

    def init(self) -> None:
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    # --- sources -----------------------------------------------------------

    def upsert_source(self, **fields: Any) -> int:
        existing = self.conn.execute(
            "SELECT id FROM sources WHERE name = ?", (fields["name"],)
        ).fetchone()
        if existing:
            return int(existing["id"])
        cols = ", ".join(fields)
        placeholders = ", ".join("?" for _ in fields)
        cur = self.conn.execute(
            f"INSERT INTO sources ({cols}) VALUES ({placeholders})", tuple(fields.values())
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def get_source(self, source_id: int) -> dict[str, Any] | None:
        row = self.conn.execute("SELECT * FROM sources WHERE id = ?", (source_id,)).fetchone()
        return dict(row) if row else None

    def list_sources(self) -> list[dict[str, Any]]:
        rows = self.conn.execute("SELECT * FROM sources ORDER BY name").fetchall()
        return [dict(r) for r in rows]

    def delete_source(self, source_id: int) -> list[str]:
        """Delete a source and every asset from it. Returns the asset file paths removed."""
        paths = [
            r["file_path"]
            for r in self.conn.execute(
                "SELECT file_path FROM assets WHERE source_id = ?", (source_id,)
            ).fetchall()
        ]
        asset_ids = [
            r["id"]
            for r in self.conn.execute(
                "SELECT id FROM assets WHERE source_id = ?", (source_id,)
            ).fetchall()
        ]
        for aid in asset_ids:
            self.conn.execute("DELETE FROM assets_fts WHERE rowid = ?", (aid,))
        self.conn.execute("DELETE FROM sources WHERE id = ?", (source_id,))
        self.conn.commit()
        return paths

    # --- assets ------------------------------------------------------------

    def get_asset_by_hash(self, sha256: str) -> dict[str, Any] | None:
        row = self.conn.execute("SELECT * FROM assets WHERE sha256 = ?", (sha256,)).fetchone()
        return dict(row) if row else None

    def get_asset(self, asset_id: int) -> dict[str, Any] | None:
        row = self.conn.execute("SELECT * FROM assets WHERE id = ?", (asset_id,)).fetchone()
        return dict(row) if row else None

    def insert_asset(self, fields: dict[str, Any]) -> int:
        cols = ", ".join(fields)
        placeholders = ", ".join("?" for _ in fields)
        cur = self.conn.execute(
            f"INSERT INTO assets ({cols}) VALUES ({placeholders})", tuple(fields.values())
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def set_embedding(self, asset_id: int, blob: bytes, dim: int) -> None:
        self.conn.execute(
            "UPDATE assets SET embedding = ?, embed_dim = ? WHERE id = ?", (blob, dim, asset_id)
        )
        self.conn.commit()

    def all_embeddings(self) -> list[tuple[int, bytes, int]]:
        rows = self.conn.execute(
            "SELECT id, embedding, embed_dim FROM assets WHERE embedding IS NOT NULL"
        ).fetchall()
        return [(int(r["id"]), r["embedding"], int(r["embed_dim"])) for r in rows]

    def all_phashes(self) -> list[tuple[int, str]]:
        rows = self.conn.execute(
            "SELECT id, phash FROM assets WHERE phash IS NOT NULL AND phash != ''"
        ).fetchall()
        return [(int(r["id"]), str(r["phash"])) for r in rows]

    def delete_asset(self, asset_id: int) -> str | None:
        row = self.conn.execute(
            "SELECT file_path FROM assets WHERE id = ?", (asset_id,)
        ).fetchone()
        if not row:
            return None
        self.conn.execute("DELETE FROM assets_fts WHERE rowid = ?", (asset_id,))
        self.conn.execute("DELETE FROM assets WHERE id = ?", (asset_id,))
        self.conn.commit()
        return str(row["file_path"])

    def list_assets(
        self,
        *,
        limit: int = 60,
        offset: int = 0,
        pixel_art_only: bool = False,
        license: str | None = None,
        source_id: int | None = None,
        tag: str | None = None,
        min_w: int | None = None,
        max_w: int | None = None,
    ) -> list[dict[str, Any]]:
        clauses, params = [], []
        if pixel_art_only:
            clauses.append("is_pixel_art = 1")
        if license:
            clauses.append("license = ?")
            params.append(license)
        if source_id is not None:
            clauses.append("source_id = ?")
            params.append(source_id)
        if min_w is not None:
            clauses.append("width >= ?")
            params.append(min_w)
        if max_w is not None:
            clauses.append("width <= ?")
            params.append(max_w)
        if tag:
            clauses.append("id IN (SELECT asset_id FROM tags WHERE tag = ?)")
            params.append(tag)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self.conn.execute(
            f"SELECT * FROM assets {where} ORDER BY id DESC LIMIT ? OFFSET ?",
            (*params, limit, offset),
        ).fetchall()
        return [dict(r) for r in rows]

    def count_assets(self) -> int:
        return int(self.conn.execute("SELECT COUNT(*) AS n FROM assets").fetchone()["n"])

    # --- tags & colours ----------------------------------------------------

    def add_tags(self, asset_id: int, tags: list[str], origin: str = "user") -> None:
        for tag in {t.strip().lower() for t in tags if t.strip()}:
            self.conn.execute(
                "INSERT OR IGNORE INTO tags (asset_id, tag, origin) VALUES (?, ?, ?)",
                (asset_id, tag, origin),
            )
        self.conn.commit()

    def get_tags(self, asset_id: int) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT tag, origin FROM tags WHERE asset_id = ? ORDER BY tag", (asset_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    def set_colors(self, asset_id: int, colors: list[tuple[int, int, int]]) -> None:
        self.conn.execute("DELETE FROM asset_colors WHERE asset_id = ?", (asset_id,))
        for rank, (r, g, b) in enumerate(colors):
            self.conn.execute(
                "INSERT INTO asset_colors (asset_id, rank, r, g, b) VALUES (?, ?, ?, ?, ?)",
                (asset_id, rank, r, g, b),
            )
        self.conn.commit()

    def get_colors(self, asset_id: int) -> list[tuple[int, int, int]]:
        rows = self.conn.execute(
            "SELECT r, g, b FROM asset_colors WHERE asset_id = ? ORDER BY rank", (asset_id,)
        ).fetchall()
        return [(int(r["r"]), int(r["g"]), int(r["b"])) for r in rows]

    def color_index(self) -> list[tuple[int, int, int, int]]:
        """(asset_id, r, g, b) for every stored dominant colour — used by colour search."""
        rows = self.conn.execute("SELECT asset_id, r, g, b FROM asset_colors").fetchall()
        return [(int(r["asset_id"]), int(r["r"]), int(r["g"]), int(r["b"])) for r in rows]

    # --- full-text search --------------------------------------------------

    def sync_fts(self, asset_id: int) -> None:
        asset = self.get_asset(asset_id)
        if not asset:
            return
        source = self.get_source(asset["source_id"]) if asset["source_id"] else None
        tags = " ".join(t["tag"] for t in self.get_tags(asset_id))
        notes = ""
        if asset.get("notes_json"):
            try:
                notes = " ".join(json.loads(asset["notes_json"]).get("notes", []))
            except (ValueError, TypeError):
                notes = ""
        self.conn.execute("DELETE FROM assets_fts WHERE rowid = ?", (asset_id,))
        self.conn.execute(
            "INSERT INTO assets_fts (rowid, title, creator, source_name, tags, notes) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                asset_id,
                asset.get("title") or "",
                asset.get("creator") or "",
                source["name"] if source else "",
                tags,
                notes,
            ),
        )
        self.conn.commit()

    def search_fts(self, query: str, limit: int = 60) -> list[int]:
        try:
            rows = self.conn.execute(
                "SELECT rowid FROM assets_fts WHERE assets_fts MATCH ? LIMIT ?",
                (query, limit),
            ).fetchall()
        except sqlite3.OperationalError:
            # Fall back to a LIKE scan if the query has FTS-unfriendly syntax.
            like = f"%{query}%"
            rows = self.conn.execute(
                "SELECT id AS rowid FROM assets WHERE title LIKE ? OR creator LIKE ? LIMIT ?",
                (like, like, limit),
            ).fetchall()
        return [int(r["rowid"]) for r in rows]


def open_db(path: Path) -> Database:
    path.parent.mkdir(parents=True, exist_ok=True)
    db = Database(path)
    db.init()
    return db
