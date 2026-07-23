"""Archive adapter: ZIP extraction, and the runner ingesting a CC0 asset pack (Kenney/OGA style).

Fully offline — the pack ZIP is built in memory and returned by a fake fetcher."""

from __future__ import annotations

import io
import zipfile

import pytest

from studylab.config import Settings
from studylab.db import Database
from studylab.scraper.allowlist import AllowlistError, parse_allowlist
from studylab.scraper.archive import ArchiveAdapter, extract_images, is_archive_url, member_title
from studylab.scraper.fetch import FetchResponse
from studylab.scraper.robots import RobotsCache
from studylab.scraper.runner import RunOptions, run_source

from .conftest import noise_png, sprite_png


def _make_pack(*, with_noise: bool = False) -> bytes:
    """A ZIP shaped like a real asset pack: images in subfolders + a readme to be ignored."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("pack/tiles/tile_00.png", sprite_png(1))
        zf.writestr("pack/tiles/tile_01.png", sprite_png(2))
        zf.writestr("pack/characters/hero.png", sprite_png(3))
        zf.writestr("pack/README.txt", b"CC0 - do whatever you want")
        zf.writestr("pack/empty/", b"")  # a directory entry
        if with_noise:
            zf.writestr("pack/photo.png", noise_png(9))
    return buf.getvalue()


# --- extraction -------------------------------------------------------------


def test_extract_images_returns_only_images() -> None:
    members = extract_images(_make_pack())
    names = [n for n, _ in members]
    assert len(members) == 3
    assert all(n.endswith(".png") for n in names)
    assert "pack/README.txt" not in names
    assert not any(n.endswith("/") for n in names)  # no directory entries


def test_member_title_is_readable() -> None:
    assert member_title("kenney-roguelike", "pack/tiles/tile_42.png") == "kenney-roguelike / tile_42"
    assert member_title(None, "hero.png") == "hero"


def test_is_archive_url() -> None:
    assert is_archive_url("https://kenney.nl/packs/roguelike.zip")
    assert is_archive_url("https://x/y.ZIP?token=1")
    assert not is_archive_url("https://x/sprite.png")


# --- adapter ----------------------------------------------------------------


def _archive_source(**over: object):
    text = (
        '[sources.kenney]\nadapter="archive"\nenabled=true\n'
        'rate_limit_per_sec=5\nmax_items=10\nallowed_licenses=["CC0-1.0"]\n'
        'default_creator="Kenney (kenney.nl)"\n'
        'urls=["https://kenney.nl/packs/roguelike.zip"]\n'
    )
    src = parse_allowlist(text)[0]
    for k, v in over.items():
        setattr(src, k, v)
    return src


def test_adapter_marks_zip_as_archive_and_png_as_image() -> None:
    src = _archive_source(urls=["https://x/pack.zip", "https://x/single.png"])
    cands = ArchiveAdapter().candidates(src, fetcher=None)  # type: ignore[arg-type]
    assert cands[0].kind == "archive" and cands[0].license == "CC0-1.0"
    assert cands[0].creator == "Kenney (kenney.nl)"
    assert cands[1].kind == "image"


# --- runner infra -----------------------------------------------------------

PACK_URL = "https://kenney.nl/packs/roguelike.zip"


class FakePackFetcher:
    def __init__(self, pack: bytes) -> None:
        self.pack = pack
        self.calls: list[str] = []

    def get(self, url: str) -> FetchResponse:
        self.calls.append(url)
        if url == PACK_URL:
            return FetchResponse(url, 200, "application/zip", self.pack)
        raise RuntimeError(f"unexpected fetch {url}")


class AllowRobots(RobotsCache):
    def __init__(self) -> None:  # noqa: D107
        pass

    def can_fetch(self, url: str) -> bool:  # type: ignore[override]
        return True


def test_runner_ingests_pack_as_cc0(db: Database, settings: Settings) -> None:
    report = run_source(
        db, settings, _archive_source(), options=RunOptions(dry_run=False),
        fetcher=FakePackFetcher(_make_pack()), robots=AllowRobots(),
    )
    assert db.count_assets() == 3
    for asset in db.list_assets(limit=10):
        assert asset["license"] == "CC0-1.0"
        assert asset["creator"] == "Kenney (kenney.nl)"
        assert asset["attribution"]
    outcome = report.outcomes[0]
    assert outcome.status == "imported"
    assert "3 images" in outcome.message


def test_dry_run_does_not_download_pack(db: Database, settings: Settings) -> None:
    fetch = FakePackFetcher(_make_pack())
    report = run_source(
        db, settings, _archive_source(), options=RunOptions(dry_run=True),
        fetcher=fetch, robots=AllowRobots(),
    )
    assert report.counts().get("planned") == 1
    assert db.count_assets() == 0
    assert PACK_URL not in fetch.calls  # never fetched in a dry-run


def test_require_pixel_art_filters_pack_members(db: Database, settings: Settings) -> None:
    report = run_source(
        db, settings, _archive_source(require_pixel_art=True),
        options=RunOptions(dry_run=False),
        fetcher=FakePackFetcher(_make_pack(with_noise=True)), robots=AllowRobots(),
    )
    # 3 sprites imported, the noise image skipped.
    assert db.count_assets() == 3
    assert "skipped" in report.outcomes[0].message


def test_resume_skips_already_ingested_pack(db: Database, settings: Settings) -> None:
    src = _archive_source()
    run_source(db, settings, src, options=RunOptions(dry_run=False),
               fetcher=FakePackFetcher(_make_pack()), robots=AllowRobots())
    report = run_source(db, settings, src, options=RunOptions(dry_run=False),
                        fetcher=FakePackFetcher(_make_pack()), robots=AllowRobots())
    assert report.counts().get("skipped-resume") == 1
    assert db.count_assets() == 3  # unchanged


def test_non_zip_body_is_refused(db: Database, settings: Settings) -> None:
    class BadFetcher:
        def get(self, url: str) -> FetchResponse:
            return FetchResponse(url, 200, "text/html", b"<html>not a zip</html>")

    report = run_source(
        db, settings, _archive_source(), options=RunOptions(dry_run=False),
        fetcher=BadFetcher(), robots=AllowRobots(),
    )
    assert report.outcomes[0].status == "refused"
    assert db.count_assets() == 0


# --- allowlist --------------------------------------------------------------


def test_allowlist_accepts_archive_adapter() -> None:
    src = parse_allowlist(
        '[sources.k]\nadapter="archive"\nallowed_licenses=["CC0-1.0"]\nurls=["https://x/p.zip"]\n'
    )[0]
    assert src.adapter == "archive"


def test_enabled_archive_without_urls_rejected() -> None:
    with pytest.raises(AllowlistError):
        parse_allowlist(
            '[sources.k]\nadapter="archive"\nenabled=true\nallowed_licenses=["CC0-1.0"]\nurls=[]\n'
        )
