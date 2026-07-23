"""Controlled scraper: allowlist rules, license mapping, robots obedience, dry-run, resume.

No test here touches the network — the adapter's HTTP is injected via a fake :class:`Fetcher` and
robots via a fake :class:`RobotsCache`."""

from __future__ import annotations

import json

import pytest

from studylab.config import Settings
from studylab.db import Database
from studylab.scraper.allowlist import AllowlistError, parse_allowlist
from studylab.scraper.fetch import FetchResponse, RateLimiter
from studylab.scraper.robots import RobotsCache
from studylab.scraper.runner import RunOptions, run_source
from studylab.scraper.wikimedia import map_license, parse_candidates

from .conftest import sprite_png

# --- allowlist validation ---------------------------------------------------


def test_allowlist_parses_and_defaults_disabled() -> None:
    src = parse_allowlist(
        '[sources.commons]\nadapter="wikimedia"\nallowed_licenses=["CC0-1.0"]\nqueries=["x"]\n'
    )[0]
    assert src.name == "commons"
    assert src.enabled is False  # off by default
    assert src.obey_robots is True


def test_allowlist_rejects_disabled_robots() -> None:
    with pytest.raises(AllowlistError):
        parse_allowlist(
            '[sources.bad]\nadapter="wikimedia"\nobey_robots=false\n'
            'allowed_licenses=["CC0-1.0"]\nqueries=["x"]\n'
        )


def test_allowlist_rejects_non_allowlist_license() -> None:
    with pytest.raises(AllowlistError):
        parse_allowlist(
            '[sources.bad]\nadapter="wikimedia"\nallowed_licenses=["CC-BY-NC-4.0"]\nqueries=["x"]\n'
        )


def test_allowlist_rejects_unknown_adapter() -> None:
    with pytest.raises(AllowlistError):
        parse_allowlist(
            '[sources.bad]\nadapter="ftp-crawler"\nallowed_licenses=["CC0-1.0"]\nqueries=["x"]\n'
        )


def test_disabled_direct_template_without_urls_still_loads() -> None:
    # A template (like sources.example.toml) with its URLs commented out must load;
    # the "needs a url" completeness check only fires once the source is enabled.
    src = parse_allowlist(
        '[sources.picks]\nadapter="direct"\nallowed_licenses=["CC0-1.0"]\nurls=[]\n'
    )[0]
    assert src.enabled is False and src.urls == []
    with pytest.raises(AllowlistError):
        parse_allowlist(
            '[sources.picks]\nadapter="direct"\nenabled=true\nallowed_licenses=["CC0-1.0"]\nurls=[]\n'
        )


def test_example_config_file_loads() -> None:
    from pathlib import Path

    from studylab.scraper.allowlist import load_allowlist

    example = Path(__file__).resolve().parent.parent / "sources.example.toml"
    sources = load_allowlist(example)
    assert {s.name for s in sources}  # parses without error
    assert all(not s.enabled for s in sources)  # nothing enabled by default


# --- license mapping + candidate parsing ------------------------------------


def test_license_mapping() -> None:
    assert map_license("cc0") == "CC0-1.0"
    assert map_license("CC BY-SA 4.0") == "CC-BY-SA-4.0"
    assert map_license("Public Domain") == "PD"
    assert map_license("cc-by-nc-4.0") is None
    assert map_license(None) is None


def _commons_payload() -> dict:
    return {
        "query": {
            "pages": {
                "1": {
                    "title": "File:Good.png",
                    "imageinfo": [{
                        "url": "https://upload.wikimedia.org/good.png",
                        "descriptionurl": "https://commons.wikimedia.org/wiki/File:Good.png",
                        "mime": "image/png",
                        "extmetadata": {"License": {"value": "cc0"},
                                        "Artist": {"value": "<a href='x'>Jane</a>"}},
                    }],
                },
                "2": {
                    "title": "File:Bad.png",
                    "imageinfo": [{
                        "url": "https://upload.wikimedia.org/bad.png",
                        "mime": "image/png",
                        "extmetadata": {"License": {"value": "cc-by-nc-4.0"}},
                    }],
                },
            }
        }
    }


def test_parse_candidates_filters_by_license_and_strips_html() -> None:
    cands = parse_candidates(_commons_payload(), {"CC0-1.0", "PD"})
    assert len(cands) == 1  # NC-licensed one dropped
    assert cands[0].license == "CC0-1.0"
    assert cands[0].creator == "Jane"  # HTML stripped
    assert cands[0].title == "Good.png"


# --- fake infra for the runner ----------------------------------------------

IMG_GOOD = "https://upload.wikimedia.org/good.png"
IMG_BAD = "https://upload.wikimedia.org/bad.png"


class FakeFetcher:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def get(self, url: str) -> FetchResponse:
        self.calls.append(url)
        if "api.php" in url:
            return FetchResponse(url, 200, "application/json",
                                 json.dumps(_commons_payload()).encode())
        if url == IMG_GOOD:
            return FetchResponse(url, 200, "image/png", sprite_png(11))
        raise RuntimeError(f"unexpected fetch {url}")


class FakeRobots(RobotsCache):
    def __init__(self, allow: bool = True) -> None:
        self.allow = allow

    def can_fetch(self, url: str) -> bool:  # type: ignore[override]
        return self.allow


def _source(**over: object):
    text = (
        '[sources.commons]\nadapter="wikimedia"\nenabled=true\n'
        'rate_limit_per_sec=5\nmax_items=10\nallowed_licenses=["CC0-1.0","PD"]\n'
        'queries=["pixel art"]\n'
    )
    src = parse_allowlist(text)[0]
    for k, v in over.items():
        setattr(src, k, v)
    return src


def test_dry_run_plans_allowed_and_downloads_nothing(db: Database, settings: Settings) -> None:
    fetch = FakeFetcher()
    report = run_source(
        db, settings, _source(), options=RunOptions(dry_run=True),
        fetcher=fetch, robots=FakeRobots(True),
    )
    assert report.counts().get("planned") == 1  # only the CC0 file
    assert db.count_assets() == 0  # nothing stored in a dry-run
    assert IMG_GOOD not in fetch.calls  # image never downloaded


def test_real_run_imports_allowed_only(db: Database, settings: Settings) -> None:
    report = run_source(
        db, settings, _source(), options=RunOptions(dry_run=False),
        fetcher=FakeFetcher(), robots=FakeRobots(True),
    )
    assert report.counts().get("imported") == 1
    assert db.count_assets() == 1
    stored = db.list_assets(limit=10)[0]
    assert stored["license"] == "CC0-1.0"
    assert stored["attribution"]  # attribution recorded


def test_robots_disallow_skips_everything(db: Database, settings: Settings) -> None:
    report = run_source(
        db, settings, _source(), options=RunOptions(dry_run=False),
        fetcher=FakeFetcher(), robots=FakeRobots(False),
    )
    assert report.counts().get("skipped-robots") == 1
    assert db.count_assets() == 0


def test_resume_skips_already_processed(db: Database, settings: Settings) -> None:
    src = _source()
    run_source(db, settings, src, options=RunOptions(dry_run=False),
               fetcher=FakeFetcher(), robots=FakeRobots(True))
    # Second run should not re-import; the job state marks the URL done.
    report = run_source(db, settings, src, options=RunOptions(dry_run=False),
                        fetcher=FakeFetcher(), robots=FakeRobots(True))
    assert report.counts().get("skipped-resume") == 1
    assert db.count_assets() == 1


def test_disabled_source_refuses_to_run(db: Database, settings: Settings) -> None:
    with pytest.raises(ValueError):
        run_source(db, settings, _source(enabled=False), fetcher=FakeFetcher())


def test_rate_limiter_spaces_requests() -> None:
    clock = {"t": 0.0}
    slept: list[float] = []
    limiter = RateLimiter(
        rate_per_sec=2.0,  # 0.5s spacing
        monotonic=lambda: clock["t"],
        sleep=lambda s: (slept.append(s), clock.__setitem__("t", clock["t"] + s)),
    )
    limiter.wait("https://host/a")
    limiter.wait("https://host/b")  # same host → must wait ~0.5s
    assert slept and abs(slept[0] - 0.5) < 1e-6
