"""Archive adapter — ingest CC0 asset *packs* (Kenney, OpenGameArt, itch.io CC0 bundles, …).

Kenney and OpenGameArt distribute art as downloadable ZIP packs with a single declared license
(Kenney is uniformly CC0; OpenGameArt packs each state their own). This adapter takes a curated list
of pack URLs (or plain image URLs) whose license you've verified, and yields one candidate per URL.
The runner downloads each pack **once** (rate-limited and robots-checked like everything else),
this module extracts its image members in memory, and each sprite is imported under the pack's
declared license with attribution.

Because the maintainer asserts the license in ``sources.toml`` (exactly as with the ``direct``
adapter), an ``archive`` source should list a single, correct license in ``allowed_licenses`` — the
one that applies to every listed pack. Extraction is a pure function over bytes, so it is fully
tested offline with no network.
"""

from __future__ import annotations

import io
import zipfile

from studylab.logging_setup import get_logger
from studylab.scraper.fetch import Fetcher
from studylab.scraper.models import Candidate, SourceConfig

log = get_logger("archive")

IMAGE_SUFFIXES = (".png", ".gif", ".bmp", ".jpg", ".jpeg", ".webp", ".tiff")

# Zip-bomb guards: cap how much we'll extract from a single pack.
MAX_MEMBERS = 2000
MAX_TOTAL_BYTES = 300 * 1024 * 1024  # 300 MiB uncompressed, across the whole pack
MAX_MEMBER_BYTES = 40 * 1024 * 1024  # 40 MiB per image


def looks_like_zip(data: bytes) -> bool:
    return data[:4] in (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")


def is_archive_url(url: str) -> bool:
    return url.lower().split("?", 1)[0].rstrip("/").endswith(".zip")


def extract_images(data: bytes) -> list[tuple[str, bytes]]:
    """Return ``(member_name, image_bytes)`` for every image inside a ZIP, with bomb guards.

    Member names are used only for titles — bytes are content-addressed on import — so a malicious
    path cannot escape any directory (nothing is written using these names).
    """
    out: list[tuple[str, bytes]] = []
    total = 0
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        infos = [i for i in zf.infolist() if not i.is_dir()]
        for info in infos[:MAX_MEMBERS]:
            name = info.filename
            if not name.lower().endswith(IMAGE_SUFFIXES):
                continue
            if info.file_size > MAX_MEMBER_BYTES:
                log.warning("skipping oversized member %s (%d bytes)", name, info.file_size)
                continue
            total += info.file_size
            if total > MAX_TOTAL_BYTES:
                log.warning("archive exceeds %d uncompressed bytes — stopping extraction", MAX_TOTAL_BYTES)
                break
            with zf.open(info) as fh:
                out.append((name, fh.read()))
    return out


def member_title(pack_title: str | None, member_name: str) -> str:
    """A readable title like ``kenney-roguelike / tile_0042`` from the pack + member path."""
    stem = member_name.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    return f"{pack_title} / {stem}" if pack_title else stem


class ArchiveAdapter:
    """Yields one candidate per configured pack/image URL, under the source's declared license."""

    name = "archive"

    def candidates(self, source: SourceConfig, fetcher: Fetcher) -> list[Candidate]:  # noqa: ARG002
        license = source.allowed_licenses[0]
        out: list[Candidate] = []
        for url in source.urls[: source.max_items]:
            title = url.rstrip("/").rsplit("/", 1)[-1] or None
            out.append(
                Candidate(
                    download_url=url,
                    page_url=source.homepage or url,
                    title=title,
                    creator=source.default_creator,
                    license=license,
                    kind="archive" if is_archive_url(url) else "image",
                )
            )
        return out
