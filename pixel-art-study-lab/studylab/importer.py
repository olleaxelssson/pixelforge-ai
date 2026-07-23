"""Import pipeline: bytes/file/folder → validated, analyzed, deduplicated, provenance-tracked asset.

Every path funnels through :func:`import_bytes`, which hashes, checks for exact and near duplicates,
copies the file into the content-addressed store, builds a display thumbnail, runs the full analysis,
and writes one fully-attributed asset row. GIFs and sprite sheets are recognised and their frame /
grid layout recorded (the sheet is stored as a single asset with its layout metadata).
"""

from __future__ import annotations

import io
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PIL import Image, UnidentifiedImageError

from studylab.analysis import analyze, rebuild_digest
from studylab.analysis.vlm import describe
from studylab.config import Settings
from studylab.db import Database
from studylab.dedup import DuplicateWarning, near_duplicates
from studylab.hashing import sha256_bytes
from studylab.logging_setup import get_logger
from studylab.provenance import build_attribution, require_collectable

log = get_logger("importer")

IMAGE_SUFFIXES = {".png", ".gif", ".bmp", ".jpg", ".jpeg", ".webp", ".tiff"}
_EXT = {"PNG": ".png", "GIF": ".gif", "BMP": ".bmp", "JPEG": ".jpg", "WEBP": ".webp", "TIFF": ".tiff"}


@dataclass
class ImportRequest:
    source_id: int
    license: str = "self"
    creator: str | None = None
    title: str | None = None
    source_url: str | None = None
    tags: list[str] = field(default_factory=list)
    attribution_template: str | None = None
    require_allowed: bool = False  # scraper sets True; local imports trust the user
    require_pixel_art: bool = False  # optionally skip non-pixel-art
    manual_override: bool = False  # force is_pixel_art regardless of the heuristic


@dataclass
class ImportResult:
    status: str  # 'imported' | 'duplicate' | 'refused' | 'skipped'
    asset_id: int | None = None
    message: str = ""
    warnings: list[dict[str, Any]] = field(default_factory=list)
    digest: str = ""


def _make_thumb(image: Image.Image, max_side: int = 256) -> Image.Image:
    img = image.convert("RGBA")
    w, h = img.size
    longest = max(w, h)
    if longest >= max_side:
        f = max_side / longest
        return img.resize((max(1, int(w * f)), max(1, int(h * f))), Image.Resampling.NEAREST)
    factor = max(1, 128 // max(1, longest))
    return img.resize((w * factor, h * factor), Image.Resampling.NEAREST)


def import_bytes(
    db: Database, settings: Settings, data: bytes, req: ImportRequest
) -> ImportResult:
    settings.ensure_dirs()
    sha = sha256_bytes(data)

    existing = db.get_asset_by_hash(sha)
    if existing:
        return ImportResult("duplicate", existing["id"], "identical file already in library")

    try:
        image = Image.open(io.BytesIO(data))
        image.load()
    except (UnidentifiedImageError, OSError) as exc:
        return ImportResult("refused", None, f"not a readable image: {exc}")

    if req.require_allowed:
        require_collectable(req.license)  # raises ProvenanceError → caller handles

    result = analyze(image)
    columns = dict(result.columns)
    if req.manual_override:
        columns["is_pixel_art"] = 1
    if req.require_pixel_art and not columns["is_pixel_art"] and not req.manual_override:
        return ImportResult("skipped", None, "does not look like pixel art (use override to force)")

    warnings = near_duplicates(db, phash=result.phash, embedding=result.embedding)

    # Content-addressed store + thumbnail.
    ext = _EXT.get((image.format or "").upper(), Path(req.title or "").suffix.lower() or ".png")
    rel_path = f"{sha}{ext}"
    (settings.assets_dir / rel_path).write_bytes(data)
    thumb_rel = f"{sha}.png"
    _make_thumb(image).save(settings.thumbs_dir / thumb_rel)

    source = db.get_source(req.source_id) or {}
    attribution = build_attribution(
        license=req.license,
        creator=req.creator,
        title=req.title,
        source_url=req.source_url,
        template=req.attribution_template or source.get("attribution_template"),
    )

    auto = describe(settings.assets_dir / rel_path, result.analysis, "local", None)
    all_tags = sorted({*(t.lower() for t in req.tags), *auto.tags})
    result.analysis["auto_caption"] = auto.caption
    digest = rebuild_digest(result.analysis, license=req.license, tags=all_tags)

    row = {
        "sha256": sha,
        "source_id": req.source_id,
        "title": req.title,
        "creator": req.creator,
        "license": req.license,
        "attribution": attribution,
        "source_url": req.source_url,
        "collected_at": _now(),
        "file_path": rel_path,
        "thumb_path": thumb_rel,
        "manual_override": int(req.manual_override),
        "silhouette_coverage": columns.pop("silhouette_coverage"),
        "phash": result.phash,
        "analysis_json": json.dumps(result.analysis),
        "notes_json": json.dumps(result.analysis["notes"]),
        "embedding": result.embedding.astype("float32").tobytes(),
        "embed_dim": int(result.embedding.shape[0]),
        **columns,
    }
    asset_id = db.insert_asset(row)
    db.set_colors(asset_id, result.dominant[:8])
    if req.tags:
        db.add_tags(asset_id, req.tags, "user")
    if auto.tags:
        db.add_tags(asset_id, auto.tags, "auto")
    db.sync_fts(asset_id)

    log.info("imported asset %s (%s, %s)", asset_id, req.license, rel_path)
    return ImportResult(
        "imported",
        asset_id,
        "imported",
        warnings=[{"asset_id": w.asset_id, "kind": w.kind, "score": w.score} for w in warnings],
        digest=digest,
    )


def import_file(db: Database, settings: Settings, path: Path, req: ImportRequest) -> ImportResult:
    if not req.title:
        req = ImportRequest(**{**req.__dict__, "title": path.stem})
    return import_bytes(db, settings, path.read_bytes(), req)


def import_folder(
    db: Database,
    settings: Settings,
    folder: Path,
    *,
    source_id: int,
    license: str = "self",
    creator: str | None = None,
    recursive: bool = True,
    tags: list[str] | None = None,
) -> list[ImportResult]:
    files = (folder.rglob("*") if recursive else folder.glob("*"))
    results: list[ImportResult] = []
    for path in sorted(files):
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES:
            req = ImportRequest(
                source_id=source_id,
                license=license,
                creator=creator,
                title=path.stem,
                source_url=path.as_uri(),
                tags=list(tags or []),
            )
            try:
                results.append(import_file(db, settings, path, req))
            except Exception as exc:  # noqa: BLE001 — one bad file shouldn't abort the batch
                log.error("failed to import %s: %s", path, exc)
                results.append(ImportResult("refused", None, str(exc)))
    return results


def _now() -> str:
    import datetime

    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def _duplicate_warning_dicts(warnings: list[DuplicateWarning]) -> list[dict[str, Any]]:
    return [{"asset_id": w.asset_id, "kind": w.kind, "score": w.score} for w in warnings]
