"""Scraper data models: a source's collection policy and a single fetch candidate."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SourceConfig:
    name: str
    adapter: str  # 'wikimedia' | 'direct' | 'archive'
    enabled: bool = False
    homepage: str = ""
    terms_url: str = ""
    rate_limit_per_sec: float = 0.5
    max_items: int = 40
    allowed_licenses: list[str] = field(default_factory=list)
    queries: list[str] = field(default_factory=list)
    urls: list[str] = field(default_factory=list)  # for the 'direct' / 'archive' adapters
    attribution_template: str | None = None
    obey_robots: bool = True  # must stay True; a False value is rejected on load
    require_pixel_art: bool = False  # skip pack members that don't look like pixel art
    default_creator: str | None = None  # e.g. "Kenney (kenney.nl)"; recorded on every asset


@dataclass
class Candidate:
    """One item the adapter proposes to collect, with its provenance resolved up front.

    ``kind`` is ``"image"`` for a single image URL, or ``"archive"`` for a downloadable pack
    (e.g. a ZIP) whose image members are extracted and imported individually.
    """

    download_url: str
    page_url: str
    title: str
    creator: str | None
    license: str
    attribution: str | None = None
    kind: str = "image"  # 'image' | 'archive'
