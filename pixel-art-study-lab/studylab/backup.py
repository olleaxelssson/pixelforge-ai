"""Export, import and backup — so a library is portable and never a black box.

Two distinct operations:

* **Dataset export/import** (:func:`export_dataset` / :func:`import_dataset`) — a portable ``.zip``
  containing a human-readable ``manifest.jsonl`` (one JSON line per asset: full provenance, license,
  attribution, tags, analysis digest) plus the original image files. Importing re-runs each file
  through the normal import pipeline with its recorded provenance, so dedup, analysis and validation
  all apply and two libraries can be merged safely.

* **Full backup/restore** (:func:`backup` / :func:`restore`) — a straight archive of the entire data
  directory (SQLite DB + assets + thumbnails) for disaster recovery.

The manifest is deliberately plain text so the library is inspectable and survives this tool.
"""

from __future__ import annotations

import io
import json
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from studylab.config import Settings
from studylab.db import Database
from studylab.importer import ImportRequest, import_bytes
from studylab.logging_setup import get_logger

log = get_logger("backup")

MANIFEST_NAME = "manifest.jsonl"


def export_records(db: Database) -> list[dict[str, Any]]:
    """One portable record per asset (provenance + tags + digest), independent of storage layout."""
    records: list[dict[str, Any]] = []
    for asset in db.list_assets(limit=1_000_000):
        aid = int(asset["id"])
        source = db.get_source(asset["source_id"]) if asset["source_id"] else None
        tags = db.get_tags(aid)
        records.append(
            {
                "sha256": asset["sha256"],
                "title": asset["title"],
                "creator": asset["creator"],
                "license": asset["license"],
                "attribution": asset["attribution"],
                "source_url": asset["source_url"],
                "source_name": source["name"] if source else None,
                "source_kind": source["kind"] if source else "local",
                "collected_at": asset["collected_at"],
                "file_path": asset["file_path"],
                "manual_override": bool(asset["manual_override"]),
                "tags_user": [t["tag"] for t in tags if t["origin"] == "user"],
                "digest": _digest_of(asset),
            }
        )
    return records


def _digest_of(asset: dict[str, Any]) -> str:
    try:
        from studylab.analysis import rebuild_digest

        analysis = json.loads(asset["analysis_json"]) if asset.get("analysis_json") else {}
        return rebuild_digest(analysis, license=asset.get("license"), tags=[])
    except Exception:  # noqa: BLE001 — digest is informational only
        return ""


def export_dataset(db: Database, settings: Settings, out_path: Path) -> Path:
    """Write a portable ``.zip`` (manifest.jsonl + original files). Returns the archive path."""
    out_path = out_path.with_suffix(".zip") if out_path.suffix != ".zip" else out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    records = export_records(db)
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        lines = "\n".join(json.dumps(r, ensure_ascii=False, sort_keys=True) for r in records)
        zf.writestr(MANIFEST_NAME, lines + ("\n" if lines else ""))
        for rec in records:
            src = settings.assets_dir / rec["file_path"]
            if src.exists():
                zf.write(src, f"assets/{rec['file_path']}")
    log.info("exported %d assets to %s", len(records), out_path)
    return out_path


@dataclass
class ImportSummary:
    imported: int = 0
    duplicate: int = 0
    refused: int = 0
    skipped: int = 0

    def add(self, status: str) -> None:
        if status == "imported":
            self.imported += 1
        elif status == "duplicate":
            self.duplicate += 1
        elif status == "skipped":
            self.skipped += 1
        else:
            self.refused += 1


def import_dataset(db: Database, settings: Settings, zip_path: Path) -> ImportSummary:
    """Import every asset in an exported ``.zip`` with its recorded provenance (dedup applies)."""
    settings.ensure_dirs()
    summary = ImportSummary()
    source_ids: dict[str, int] = {}
    with zipfile.ZipFile(zip_path, "r") as zf:
        manifest = zf.read(MANIFEST_NAME).decode("utf-8")
        for line in manifest.splitlines():
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            source_name = rec.get("source_name") or "imported"
            if source_name not in source_ids:
                source_ids[source_name] = _ensure_source(db, source_name, rec.get("source_kind"))
            try:
                data = zf.read(f"assets/{rec['file_path']}")
            except KeyError:
                summary.refused += 1
                log.warning("manifest references missing file %s", rec["file_path"])
                continue
            req = ImportRequest(
                source_id=source_ids[source_name],
                license=rec.get("license") or "self",
                creator=rec.get("creator"),
                title=rec.get("title"),
                source_url=rec.get("source_url"),
                tags=list(rec.get("tags_user") or []),
                manual_override=bool(rec.get("manual_override")),
            )
            result = import_bytes(db, settings, data, req)
            summary.add(result.status)
    log.info("imported dataset from %s: %s", zip_path, summary)
    return summary


def _ensure_source(db: Database, name: str, kind: str | None) -> int:
    import datetime

    return db.upsert_source(
        name=name,
        kind=kind or "local",
        added_at=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
    )


def backup(settings: Settings, out_path: Path) -> Path:
    """Archive the whole data directory (DB + assets + thumbnails) for disaster recovery."""
    out_path = out_path.with_suffix(".zip") if out_path.suffix != ".zip" else out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # Checkpoint the WAL so the copied DB file is complete.
    try:
        db = Database(settings.db_path)
        db.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        db.close()
    except Exception:  # noqa: BLE001 — a missing/locked DB just means a smaller backup
        pass
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(settings.data_dir.rglob("*")):
            if path.is_file() and out_path not in (path, path.resolve()):
                zf.write(path, path.relative_to(settings.data_dir).as_posix())
    log.info("backed up data dir to %s", out_path)
    return out_path


def restore(settings: Settings, zip_path: Path) -> None:
    """Extract a full backup into the data directory (files are overwritten)."""
    settings.ensure_dirs()
    with zipfile.ZipFile(zip_path, "r") as zf:
        for name in zf.namelist():
            target = (settings.data_dir / name).resolve()
            if not str(target).startswith(str(settings.data_dir.resolve())):
                raise ValueError(f"unsafe path in archive: {name}")  # zip-slip guard
            if name.endswith("/"):
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(name) as src, open(target, "wb") as dst:
                dst.write(src.read())
    log.info("restored data dir from %s", zip_path)


def read_manifest(zip_path: Path) -> list[dict[str, Any]]:
    with zipfile.ZipFile(zip_path, "r") as zf:
        text = zf.read(MANIFEST_NAME).decode("utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def _bytes_io(data: bytes) -> io.BytesIO:
    return io.BytesIO(data)
