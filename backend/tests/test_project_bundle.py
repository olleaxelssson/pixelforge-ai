"""Portable project bundle tests (M25, D-001)."""

from __future__ import annotations

import base64
import io
import zipfile
from pathlib import Path

import pytest
from PIL import Image

from pixelforge.projects.bundle import (
    SCHEMA_VERSION,
    AutosaveManager,
    ProjectBundle,
    ProjectBundleError,
    atomic_write_bytes,
    bundle_bytes,
    bundle_info,
    load_bundle,
    migrate_manifest,
    read_bundle,
    save_bundle,
)


def _png(color: tuple[int, int, int, int]) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGBA", (16, 16), color).save(buffer, format="PNG")
    return buffer.getvalue()


def _bundle() -> tuple[ProjectBundle, dict[str, bytes]]:
    images = {"hero.png": _png((200, 30, 30, 255)), "slime.png": _png((30, 120, 200, 255))}
    bundle = ProjectBundle(
        name="My Game",
        created_at=1234.0,
        sprites=["hero.png", "slime.png"],
        palettes=[{"id": "p", "colors": ["#ffffff"]}],
        metadata={"note": "x"},
    )
    return bundle, images


# --- deterministic round-trip ----------------------------------------------


def test_save_load_save_is_byte_stable() -> None:
    bundle, images = _bundle()
    first = bundle_bytes(bundle, images)
    loaded = read_bundle(first)
    second = bundle_bytes(loaded.bundle, loaded.images)
    assert first == second  # byte-identical round-trip


def test_round_trip_preserves_content() -> None:
    bundle, images = _bundle()
    loaded = read_bundle(bundle_bytes(bundle, images))
    assert loaded.bundle.name == "My Game"
    assert loaded.bundle.created_at == 1234.0
    assert loaded.bundle.sprites == ["hero.png", "slime.png"]
    assert loaded.bundle.palettes == [{"id": "p", "colors": ["#ffffff"]}]
    assert loaded.images == images  # PNG bytes carried verbatim


def test_bundle_is_a_zip_with_manifest_and_sprites() -> None:
    bundle, images = _bundle()
    with zipfile.ZipFile(io.BytesIO(bundle_bytes(bundle, images))) as archive:
        names = archive.namelist()
        assert "manifest.json" in names
        assert "sprites/hero.png" in names
        # Deterministic: everything stored (uncompressed) with the fixed zip epoch.
        for info in archive.infolist():
            assert info.compress_type == zipfile.ZIP_STORED
            assert info.date_time == (1980, 1, 1, 0, 0, 0)


def test_missing_sprite_is_rejected() -> None:
    with pytest.raises(ProjectBundleError):
        bundle_bytes(ProjectBundle(sprites=["ghost.png"]), {})


# --- disk + atomic ---------------------------------------------------------


def test_save_bundle_is_atomic(tmp_path: Path) -> None:
    bundle, images = _bundle()
    path = tmp_path / "proj.pforge"
    save_bundle(bundle, images, path)
    assert path.read_bytes() == bundle_bytes(bundle, images)
    # No temp files left behind.
    assert [p.name for p in tmp_path.iterdir()] == ["proj.pforge"]


def test_atomic_write_replaces_existing(tmp_path: Path) -> None:
    path = tmp_path / "f.bin"
    atomic_write_bytes(path, b"first")
    atomic_write_bytes(path, b"second")
    assert path.read_bytes() == b"second"
    assert [p.name for p in tmp_path.iterdir()] == ["f.bin"]


def test_bundle_info(tmp_path: Path) -> None:
    bundle, images = _bundle()
    path = tmp_path / "proj.pforge"
    save_bundle(bundle, images, path)
    info = bundle_info(path)
    assert info["name"] == "My Game"
    assert info["sprite_count"] == 2
    assert info["palette_count"] == 1
    assert info["schema_version"] == SCHEMA_VERSION


# --- migration + corruption ------------------------------------------------


def test_migrate_is_noop_for_current_version() -> None:
    raw = {"schema_version": 1, "name": "x"}
    assert migrate_manifest(dict(raw))["schema_version"] == SCHEMA_VERSION


def test_migrate_rejects_newer_schema() -> None:
    with pytest.raises(ProjectBundleError):
        migrate_manifest({"schema_version": SCHEMA_VERSION + 1})


def test_read_rejects_non_zip() -> None:
    with pytest.raises(ProjectBundleError):
        read_bundle(b"not a zip file")


def test_read_rejects_zip_without_manifest() -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("sprites/x.png", b"data")
    with pytest.raises(ProjectBundleError):
        read_bundle(buffer.getvalue())


# --- autosave / recovery ---------------------------------------------------


def test_autosave_write_and_recover(tmp_path: Path) -> None:
    bundle, images = _bundle()
    manager = AutosaveManager(tmp_path)
    assert manager.recover_latest() is None  # nothing yet
    written = manager.write(bundle, images)
    assert written == tmp_path / "autosave.pforge"
    recovered = manager.recover_latest()
    assert recovered is not None
    assert load_bundle(recovered).bundle.name == "My Game"


# --- API -------------------------------------------------------------------


def test_api_project_save_and_load(client) -> None:
    sprite = base64.b64encode(_png((200, 30, 30, 255))).decode()
    save = client.post(
        "/api/project/save",
        json={
            "name": "Demo",
            "created_at": 100.0,
            "sprites": [{"name": "a.png", "image_base64": sprite}],
        },
    )
    assert save.status_code == 200
    assert save.headers["content-disposition"] == 'attachment; filename="Demo.pforge"'

    bundle_b64 = base64.b64encode(save.content).decode()
    load = client.post("/api/project/load", json={"bundle_base64": bundle_b64})
    assert load.status_code == 200
    body = load.json()
    assert body["manifest"]["name"] == "Demo"
    assert body["manifest"]["created_at"] == 100.0
    assert [s["name"] for s in body["sprites"]] == ["a.png"]


def test_api_project_load_rejects_corrupt(client) -> None:
    bad = base64.b64encode(b"not a bundle").decode()
    assert client.post("/api/project/load", json={"bundle_base64": bad}).status_code == 422
