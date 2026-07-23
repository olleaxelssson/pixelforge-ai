"""The scraper runner — where the rules are enforced, in order, for every candidate.

For each source the runner:

1. asks the adapter what files exist for the source's queries (network happens here, via the
   injected :class:`Fetcher`);
2. drops any candidate whose license is not on *that source's* allowlist;
3. asks robots.txt whether the download URL may be fetched — a disallow means skip;
4. in **dry-run** (the default) stops there and just reports what *would* be collected;
5. otherwise downloads (rate-limited, retrying) and hands the bytes to the importer with
   ``require_allowed=True`` so the license is re-checked at the point of storage.

Progress is written to a per-source **job file** so an interrupted run resumes instead of
re-downloading everything. Nothing is ever collected from a source that is not ``enabled``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from studylab.config import Settings
from studylab.db import Database
from studylab.importer import ImportRequest, import_bytes
from studylab.logging_setup import get_logger
from studylab.provenance import ProvenanceError, build_attribution, is_allowed_license
from studylab.scraper.archive import ArchiveAdapter, extract_images, looks_like_zip, member_title
from studylab.scraper.direct import DirectAdapter
from studylab.scraper.fetch import Fetcher, FetchError, HttpFetcher
from studylab.scraper.models import Candidate, SourceConfig
from studylab.scraper.robots import RobotsCache
from studylab.scraper.wikimedia import WikimediaAdapter

log = get_logger("scraper")


class Adapter(Protocol):
    name: str

    def candidates(self, source: SourceConfig, fetcher: Fetcher) -> list[Candidate]: ...


def get_adapter(name: str) -> Adapter:
    if name == "wikimedia":
        return WikimediaAdapter()
    if name == "direct":
        return DirectAdapter()
    if name == "archive":
        return ArchiveAdapter()
    raise ValueError(f"unknown adapter: {name}")


@dataclass
class RunOptions:
    dry_run: bool = True
    limit: int | None = None
    resume: bool = True


@dataclass
class CandidateOutcome:
    download_url: str
    license: str
    status: str  # planned | imported | duplicate | skipped-* | refused | error
    title: str | None = None
    message: str = ""
    asset_id: int | None = None
    warnings: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class JobReport:
    source: str
    dry_run: bool
    outcomes: list[CandidateOutcome] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        tally: dict[str, int] = {}
        for o in self.outcomes:
            tally[o.status] = tally.get(o.status, 0) + 1
        return tally


# --- resumable job state ----------------------------------------------------

_TERMINAL = {"imported", "duplicate", "refused", "skipped-robots", "skipped-license"}


class JobState:
    """Per-source record of already-processed download URLs, so real runs are resumable."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.processed: dict[str, str] = {}
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                self.processed = dict(data.get("processed", {}))
            except (ValueError, OSError):
                self.processed = {}

    def done(self, url: str) -> bool:
        return self.processed.get(url) in _TERMINAL

    def record(self, url: str, status: str) -> None:
        if status in _TERMINAL:
            self.processed[url] = status

    def save(self, source: str) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps({"source": source, "processed": self.processed}, indent=2),
            encoding="utf-8",
        )


def _register_source(db: Database, settings: Settings, source: SourceConfig) -> int:
    import datetime

    return db.upsert_source(
        name=source.name,
        kind="scraper",
        homepage=source.homepage,
        terms_url=source.terms_url,
        license_default=(source.allowed_licenses[0] if source.allowed_licenses else None),
        attribution_template=source.attribution_template,
        added_at=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        notes=f"scraper adapter={source.adapter}",
    )


def run_source(
    db: Database,
    settings: Settings,
    source: SourceConfig,
    *,
    options: RunOptions | None = None,
    adapter: Adapter | None = None,
    fetcher: Fetcher | None = None,
    robots: RobotsCache | None = None,
) -> JobReport:
    """Collect from one enabled source, obeying license allowlist, robots.txt and rate limits."""
    options = options or RunOptions()
    if not source.enabled:
        raise ValueError(f"source '{source.name}' is not enabled; refusing to run it.")

    adapter = adapter or get_adapter(source.adapter)
    fetcher = fetcher or HttpFetcher(settings.user_agent, source.rate_limit_per_sec)
    robots = robots or RobotsCache(settings.user_agent)

    report = JobReport(source=source.name, dry_run=options.dry_run)
    state = JobState(settings.data_dir / "jobs" / f"{source.name}.json")
    source_id = _register_source(db, settings, source)

    log.info(
        "run source=%s adapter=%s dry_run=%s enabled=%s",
        source.name,
        source.adapter,
        options.dry_run,
        source.enabled,
    )

    candidates = adapter.candidates(source, fetcher)
    collected = 0
    limit = options.limit if options.limit is not None else source.max_items

    for cand in candidates:
        if collected >= limit:
            break

        # Rule 1: license must be on this source's allowlist (and the global allowlist).
        if cand.license not in source.allowed_licenses or not is_allowed_license(cand.license):
            report.outcomes.append(
                CandidateOutcome(
                    cand.download_url, cand.license, "skipped-license", cand.title,
                    f"license '{cand.license}' not permitted for this source",
                )
            )
            continue

        # Resume: don't reprocess a URL that already reached a terminal state.
        if options.resume and state.done(cand.download_url):
            report.outcomes.append(
                CandidateOutcome(
                    cand.download_url, cand.license, "skipped-resume", cand.title,
                    f"already processed ({state.processed[cand.download_url]})",
                )
            )
            continue

        # Rule 2: robots.txt must permit the download URL.
        if source.obey_robots and not robots.can_fetch(cand.download_url):
            outcome = CandidateOutcome(
                cand.download_url, cand.license, "skipped-robots", cand.title,
                "robots.txt disallows this URL",
            )
            report.outcomes.append(outcome)
            state.record(cand.download_url, outcome.status)
            continue

        if options.dry_run:
            note = "would download pack + extract images (dry-run)" if cand.kind == "archive" \
                else "would collect (dry-run)"
            report.outcomes.append(
                CandidateOutcome(cand.download_url, cand.license, "planned", cand.title, note)
            )
            collected += 1
            continue

        if cand.kind == "archive":
            outcome = _download_and_extract_archive(db, settings, source, source_id, cand, fetcher)
        else:
            outcome = _download_and_import(db, settings, source, source_id, cand, fetcher)
        report.outcomes.append(outcome)
        state.record(cand.download_url, outcome.status)
        if outcome.status in ("imported", "duplicate"):
            collected += 1

    if not options.dry_run:
        state.save(source.name)
    log.info("run source=%s complete: %s", source.name, report.counts())
    return report


def _download_and_import(
    db: Database,
    settings: Settings,
    source: SourceConfig,
    source_id: int,
    cand: Candidate,
    fetcher: Fetcher,
) -> CandidateOutcome:
    try:
        resp = fetcher.get(cand.download_url)
    except FetchError as exc:
        return CandidateOutcome(cand.download_url, cand.license, "error", cand.title, str(exc))

    if not resp.content_type.startswith("image/"):
        return CandidateOutcome(
            cand.download_url, cand.license, "refused", cand.title,
            f"not an image (content-type: {resp.content_type})",
        )

    attribution = cand.attribution or build_attribution(
        license=cand.license,
        creator=cand.creator,
        title=cand.title,
        source_url=cand.page_url,
        template=source.attribution_template,
    )
    req = ImportRequest(
        source_id=source_id,
        license=cand.license,
        creator=cand.creator,
        title=cand.title,
        source_url=cand.page_url,
        attribution_template=(source.attribution_template or attribution),
        require_allowed=True,
        require_pixel_art=source.require_pixel_art,
    )
    try:
        result = import_bytes(db, settings, resp.body, req)
    except ProvenanceError as exc:
        return CandidateOutcome(cand.download_url, cand.license, "refused", cand.title, str(exc))

    return CandidateOutcome(
        cand.download_url, cand.license, result.status, cand.title, result.message,
        asset_id=result.asset_id, warnings=result.warnings,
    )


def _download_and_extract_archive(
    db: Database,
    settings: Settings,
    source: SourceConfig,
    source_id: int,
    cand: Candidate,
    fetcher: Fetcher,
) -> CandidateOutcome:
    """Download one pack, extract its image members, and import each under the pack's license."""
    try:
        resp = fetcher.get(cand.download_url)
    except FetchError as exc:
        return CandidateOutcome(cand.download_url, cand.license, "error", cand.title, str(exc))

    if not looks_like_zip(resp.body):
        return CandidateOutcome(
            cand.download_url, cand.license, "refused", cand.title,
            "not a ZIP archive (expected a downloadable pack)",
        )

    try:
        members = extract_images(resp.body)
    except Exception as exc:  # noqa: BLE001 — a corrupt archive shouldn't abort the whole run
        return CandidateOutcome(cand.download_url, cand.license, "error", cand.title,
                                f"could not read archive: {exc}")
    if not members:
        return CandidateOutcome(cand.download_url, cand.license, "skipped", cand.title,
                                "archive contained no images")

    tally: dict[str, int] = {}
    for name, data in members:
        req = ImportRequest(
            source_id=source_id,
            license=cand.license,
            creator=cand.creator,
            title=member_title(cand.title, name),
            source_url=cand.page_url,
            attribution_template=source.attribution_template,
            require_allowed=True,
            require_pixel_art=source.require_pixel_art,
        )
        try:
            result = import_bytes(db, settings, data, req)
        except ProvenanceError as exc:
            log.error("archive member refused (%s): %s", name, exc)
            tally["refused"] = tally.get("refused", 0) + 1
            continue
        tally[result.status] = tally.get(result.status, 0) + 1

    imported = tally.get("imported", 0)
    status = "imported" if imported else ("duplicate" if tally.get("duplicate") else "skipped")
    summary = ", ".join(f"{n} {s}" for s, n in sorted(tally.items()))
    return CandidateOutcome(
        cand.download_url, cand.license, status, cand.title,
        f"pack: {len(members)} images ({summary})",
    )
