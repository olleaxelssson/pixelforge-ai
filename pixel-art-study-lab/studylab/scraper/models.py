"""Scraper data models: a source's collection policy and a single fetch candidate."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SourceConfig:
    name: str
    adapter: str  # 'wikimedia' | 'direct'
    enabled: bool = False
    homepage: str = ""
    terms_url: str = ""
    rate_limit_per_sec: float = 0.5
    max_items: int = 40
    allowed_licenses: list[str] = field(default_factory=list)
    queries: list[str] = field(default_factory=list)
    urls: list[str] = field(default_factory=list)  # for the 'direct' adapter
    attribution_template: str | None = None
    obey_robots: bool = True  # must stay True; a False value is rejected on load


@dataclass
class Candidate:
    """One image the adapter proposes to collect, with its provenance resolved up front."""

    download_url: str
    page_url: str
    title: str
    creator: str | None
    license: str
    attribution: str | None = None
