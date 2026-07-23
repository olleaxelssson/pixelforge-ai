"""Import pipeline: files, folders, GIFs, sprite sheets, validation, and exact dedup."""

from __future__ import annotations

from pathlib import Path

import pytest

from studylab.config import Settings
from studylab.db import Database
from studylab.importer import ImportRequest, import_bytes, import_folder
from studylab.provenance import ProvenanceError

from .conftest import gif_bytes, noise_png, sprite_png, strip_png


def _req(source_id: int, **kw: object) -> ImportRequest:
    return ImportRequest(source_id=source_id, **kw)  # type: ignore[arg-type]


def test_import_stores_asset_with_provenance(
    db: Database, settings: Settings, local_source: int
) -> None:
    res = import_bytes(
        db, settings, sprite_png(),
        _req(local_source, license="CC0-1.0", creator="Me", title="Hero", tags=["knight"]),
    )
    assert res.status == "imported"
    asset = db.get_asset(res.asset_id or 0)
    assert asset is not None
    assert asset["license"] == "CC0-1.0"
    assert asset["creator"] == "Me"
    assert (settings.assets_dir / asset["file_path"]).exists()
    assert (settings.thumbs_dir / asset["thumb_path"]).exists()
    tags = {t["tag"] for t in db.get_tags(res.asset_id or 0)}
    assert "knight" in tags
    assert res.digest.startswith("PALAB/1")


def test_exact_duplicate_detected_on_reimport(
    db: Database, settings: Settings, local_source: int
) -> None:
    data = sprite_png(101)
    first = import_bytes(db, settings, data, _req(local_source, license="self"))
    second = import_bytes(db, settings, data, _req(local_source, license="self"))
    assert first.status == "imported"
    assert second.status == "duplicate"
    assert second.asset_id == first.asset_id
    assert db.count_assets() == 1


def test_require_pixel_art_skips_noise_but_override_forces(
    db: Database, settings: Settings, local_source: int
) -> None:
    skipped = import_bytes(
        db, settings, noise_png(), _req(local_source, license="self", require_pixel_art=True)
    )
    assert skipped.status == "skipped"

    forced = import_bytes(
        db, settings, noise_png(),
        _req(local_source, license="self", require_pixel_art=True, manual_override=True),
    )
    assert forced.status == "imported"
    assert db.get_asset(forced.asset_id or 0)["is_pixel_art"] == 1


def test_require_allowed_refuses_bad_license(
    db: Database, settings: Settings, local_source: int
) -> None:
    with pytest.raises(ProvenanceError):
        import_bytes(
            db, settings, sprite_png(),
            _req(local_source, license="CC-BY-NC-4.0", require_allowed=True),
        )


def test_gif_and_sheet_layout_recorded(
    db: Database, settings: Settings, local_source: int
) -> None:
    gif = import_bytes(db, settings, gif_bytes(), _req(local_source, license="self", title="anim"))
    assert db.get_asset(gif.asset_id or 0)["frame_count"] >= 2

    sheet = import_bytes(db, settings, strip_png(), _req(local_source, license="self", title="walk"))
    sheet_asset = db.get_asset(sheet.asset_id or 0)
    assert sheet_asset["width"] > sheet_asset["height"]


def test_import_folder_batch(
    db: Database, settings: Settings, local_source: int, tmp_path: Path
) -> None:
    folder = tmp_path / "imgs"
    folder.mkdir()
    for i in range(3):
        (folder / f"s{i}.png").write_bytes(sprite_png(400 + i))
    (folder / "notes.txt").write_text("ignore me")
    results = import_folder(db, settings, folder, source_id=local_source, license="self")
    assert len([r for r in results if r.status == "imported"]) == 3
    assert db.count_assets() == 3
