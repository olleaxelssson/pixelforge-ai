"""Portable project bundles (M25, D-001): the single-file ``.pforge`` workspace archive.

A ``.pforge`` file is a **deterministic** zip of a ``manifest.json`` plus the workspace's PNG
assets. "Deterministic" is load-bearing: entries are written sorted, uncompressed (``ZIP_STORED``),
and with a fixed timestamp, and image bytes are carried **verbatim** (never re-encoded) — so a
``save → load → save`` round-trip is **byte-identical**, on any machine. Writes are atomic (temp
file → ``fsync`` → ``os.replace``) so a crash mid-save can never corrupt an existing file, and a
schema version + :func:`migrate_manifest` hook keeps older bundles loadable as the format evolves.
"""

from __future__ import annotations

import io
import json
import os
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from pixelforge import __version__
from pixelforge.core.errors import PixelForgeError

SCHEMA_VERSION = 1
_MANIFEST = "manifest.json"
_SPRITE_DIR = "sprites"
# A fixed zip timestamp (the zip epoch) so archives never carry a wall-clock time.
_ZIP_EPOCH = (1980, 1, 1, 0, 0, 0)


class ProjectBundleError(PixelForgeError):
    """Raised when a ``.pforge`` file is malformed or unsupported."""


class ProjectBundle(BaseModel):
    """The manifest half of a ``.pforge`` — everything except the raw PNG bytes."""

    schema_version: int = SCHEMA_VERSION
    app_version: str = __version__
    name: str = "Untitled Project"
    created_at: float = 0.0  # bundle-owned (preserved across load) so re-saves stay byte-stable
    sprites: list[str] = Field(default_factory=list)  # PNG entry names under sprites/
    palettes: list[dict[str, object]] = Field(default_factory=list)
    characters: list[dict[str, object]] = Field(default_factory=list)
    project: dict[str, object] = Field(default_factory=dict)  # embedded editor project state
    metadata: dict[str, object] = Field(default_factory=dict)


@dataclass
class LoadedBundle:
    bundle: ProjectBundle
    images: dict[str, bytes] = field(default_factory=dict)  # name -> raw PNG bytes


def migrate_manifest(raw: dict[str, Any]) -> dict[str, Any]:
    """Upgrade an older manifest dict to the current schema (forward-compatible hook)."""
    version = int(raw.get("schema_version", 1))
    if version > SCHEMA_VERSION:
        raise ProjectBundleError(
            f"bundle schema v{version} is newer than supported v{SCHEMA_VERSION}; upgrade the app"
        )
    # Future migrations bump `version` step by step here. v1 is current, so this is a no-op today.
    raw["schema_version"] = SCHEMA_VERSION
    return raw


def bundle_bytes(bundle: ProjectBundle, images: dict[str, bytes]) -> bytes:
    """Serialize a bundle + its images to deterministic ``.pforge`` bytes (no disk)."""
    missing = set(bundle.sprites) - set(images)
    if missing:
        raise ProjectBundleError(f"sprites referenced but not provided: {sorted(missing)}")

    manifest = json.dumps(bundle.model_dump(), sort_keys=True, indent=2).encode("utf-8")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED) as archive:
        _write(archive, _MANIFEST, manifest)
        for name in sorted(bundle.sprites):  # sorted → stable entry order
            _write(archive, f"{_SPRITE_DIR}/{name}", images[name])
    return buffer.getvalue()


def save_bundle(bundle: ProjectBundle, images: dict[str, bytes], path: Path) -> Path:
    """Atomically write a ``.pforge`` file (temp → fsync → replace)."""
    atomic_write_bytes(path, bundle_bytes(bundle, images))
    return path


def load_bundle(path: Path) -> LoadedBundle:
    """Read a ``.pforge`` file back into a bundle + its images."""
    return read_bundle(path.read_bytes())


def read_bundle(data: bytes) -> LoadedBundle:
    """Parse ``.pforge`` bytes into a bundle + images (migrating older manifests)."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            names = set(archive.namelist())
            if _MANIFEST not in names:
                raise ProjectBundleError("not a .pforge bundle: manifest.json missing")
            raw = json.loads(archive.read(_MANIFEST))
            bundle = ProjectBundle.model_validate(migrate_manifest(raw))
            images = {
                name.split("/", 1)[1]: archive.read(name)
                for name in sorted(names)
                if name.startswith(f"{_SPRITE_DIR}/")
            }
    except (zipfile.BadZipFile, json.JSONDecodeError, ValueError) as exc:
        raise ProjectBundleError(f"corrupt .pforge bundle: {exc}") from exc
    return LoadedBundle(bundle=bundle, images=images)


def bundle_info(path: Path) -> dict[str, object]:
    """A lightweight summary of a ``.pforge`` (manifest + asset counts) without decoding images."""
    loaded = load_bundle(path)
    b = loaded.bundle
    return {
        "name": b.name,
        "schema_version": b.schema_version,
        "app_version": b.app_version,
        "created_at": b.created_at,
        "sprite_count": len(b.sprites),
        "palette_count": len(b.palettes),
        "character_count": len(b.characters),
    }


def atomic_write_bytes(path: Path, data: bytes) -> None:
    """Write ``data`` to ``path`` atomically: a sibling temp file is fsync'd then renamed in."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    with open(tmp, "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)  # atomic on POSIX and Windows


def _write(archive: zipfile.ZipFile, name: str, data: bytes) -> None:
    info = zipfile.ZipInfo(name, date_time=_ZIP_EPOCH)
    info.compress_type = zipfile.ZIP_STORED
    info.external_attr = 0o644 << 16  # stable permissions
    archive.writestr(info, data)


class AutosaveManager:
    """Crash-recovery autosaves: atomic ``.pforge`` writes to a data dir, newest recoverable."""

    def __init__(self, data_dir: Path, prefix: str = "autosave") -> None:
        self._dir = data_dir
        self._prefix = prefix

    def path(self) -> Path:
        return self._dir / f"{self._prefix}.pforge"

    def write(self, bundle: ProjectBundle, images: dict[str, bytes]) -> Path:
        return save_bundle(bundle, images, self.path())

    def recover_latest(self) -> Path | None:
        """The most-recently-modified recoverable ``.pforge`` in the data dir, if any."""
        candidates = sorted(
            self._dir.glob(f"{self._prefix}*.pforge"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        return candidates[0] if candidates else None
