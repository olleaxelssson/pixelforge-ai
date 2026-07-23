"""Export/import (portable dataset) and full backup/restore round-trips."""

from __future__ import annotations

from pathlib import Path

from studylab.backup import (
    backup,
    export_dataset,
    import_dataset,
    read_manifest,
    restore,
)
from studylab.config import Settings
from studylab.db import Database, open_db
from studylab.importer import ImportRequest, import_bytes

from .conftest import sprite_png


def _seed(db: Database, settings: Settings, source: int) -> None:
    import_bytes(db, settings, sprite_png(1), ImportRequest(source_id=source, license="CC0-1.0",
                                                            creator="Me", title="one", tags=["hero"]))
    import_bytes(db, settings, sprite_png(2), ImportRequest(source_id=source, license="self",
                                                            title="two"))


def test_export_manifest_has_provenance(
    db: Database, settings: Settings, local_source: int, tmp_path: Path
) -> None:
    _seed(db, settings, local_source)
    zip_path = export_dataset(db, settings, tmp_path / "out.zip")
    manifest = read_manifest(zip_path)
    assert len(manifest) == 2
    rec = next(r for r in manifest if r["title"] == "one")
    assert rec["license"] == "CC0-1.0"
    assert rec["creator"] == "Me"
    assert "hero" in rec["tags_user"]
    assert rec["digest"].startswith("PALAB/1")


def test_export_then_import_into_fresh_library(
    db: Database, settings: Settings, local_source: int, tmp_path: Path
) -> None:
    _seed(db, settings, local_source)
    zip_path = export_dataset(db, settings, tmp_path / "out.zip")

    # Fresh library in a new data dir.
    fresh = Settings(data_dir=tmp_path / "fresh", vlm_api_key=None, vlm_provider="local",
                     user_agent="test")
    fresh.ensure_dirs()
    fdb = open_db(fresh.db_path)
    summary = import_dataset(fdb, fresh, zip_path)
    assert summary.imported == 2
    assert fdb.count_assets() == 2
    # Provenance preserved.
    titles = {a["title"] for a in fdb.list_assets(limit=10)}
    assert titles == {"one", "two"}
    fdb.close()


def test_import_is_idempotent_via_dedup(
    db: Database, settings: Settings, local_source: int, tmp_path: Path
) -> None:
    _seed(db, settings, local_source)
    zip_path = export_dataset(db, settings, tmp_path / "out.zip")
    summary = import_dataset(db, settings, zip_path)  # re-import into same library
    assert summary.duplicate == 2  # nothing new
    assert db.count_assets() == 2


def test_full_backup_and_restore(
    db: Database, settings: Settings, local_source: int, tmp_path: Path
) -> None:
    _seed(db, settings, local_source)
    archive = backup(settings, tmp_path / "bk.zip")
    assert archive.exists()

    target = Settings(data_dir=tmp_path / "restored", vlm_api_key=None, vlm_provider="local",
                      user_agent="test")
    restore(target, archive)
    rdb = open_db(target.db_path)
    assert rdb.count_assets() == 2
    rdb.close()
