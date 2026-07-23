"""Wikimedia Commons adapter.

Commons exposes a documented public API and hosts freely-licensed media; every file carries
machine-readable license metadata (``extmetadata``). This adapter asks the API for files matching a
query, reads each file's license, maps it onto our allowlist, and proposes only the ones whose
license the source permits — with attribution resolved up front from the ``Artist`` field.

The response-parsing step (:func:`parse_candidates`) is a pure function over already-fetched JSON,
so the mapping rules are unit-tested without any network access.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlencode

from studylab.scraper.fetch import Fetcher
from studylab.scraper.models import Candidate, SourceConfig

COMMONS_API = "https://commons.wikimedia.org/w/api.php"

# Commons' machine license tags (extmetadata.License.value) → our allowlist identifiers.
_LICENSE_MAP = {
    "cc0": "CC0-1.0",
    "cc-zero": "CC0-1.0",
    "cc0-1.0": "CC0-1.0",
    "pd": "PD",
    "public domain": "PD",
    "cc-by-4.0": "CC-BY-4.0",
    "cc-by-3.0": "CC-BY-3.0",
    "cc-by-2.5": "CC-BY-3.0",  # treat older BY as BY-3.0 for attribution purposes
    "cc-by-sa-4.0": "CC-BY-SA-4.0",
    "cc-by-sa-3.0": "CC-BY-SA-3.0",
}

_TAG_RE = re.compile(r"<[^>]+>")


def map_license(raw: str | None) -> str | None:
    """Map a Commons license tag (or short name) to an allowlist identifier, or None if unknown."""
    if not raw:
        return None
    key = raw.strip().lower()
    if key in _LICENSE_MAP:
        return _LICENSE_MAP[key]
    # Some entries only expose a human short name like "CC BY-SA 4.0".
    normalized = key.replace(" ", "-")
    if normalized in _LICENSE_MAP:
        return _LICENSE_MAP[normalized]
    if normalized.startswith("public-domain") or normalized == "no-restrictions":
        return "PD"
    return None


def _strip_html(value: str | None) -> str | None:
    if not value:
        return None
    text = _TAG_RE.sub("", value)
    return re.sub(r"\s+", " ", text).strip() or None


def build_search_url(query: str, limit: int) -> str:
    """Build the Commons API URL that searches file-namespace items and returns their imageinfo."""
    params = {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrsearch": query,
        "gsrnamespace": "6",  # File:
        "gsrlimit": str(max(1, min(limit, 500))),
        "prop": "imageinfo",
        "iiprop": "url|mime|extmetadata|size",
        "iiurlwidth": "512",
    }
    return f"{COMMONS_API}?{urlencode(params)}"


def parse_candidates(payload: dict[str, Any], allowed_licenses: set[str]) -> list[Candidate]:
    """Turn a Commons API JSON payload into collectable candidates (pure; no network)."""
    pages = (payload.get("query") or {}).get("pages") or {}
    out: list[Candidate] = []
    for page in pages.values():
        infos = page.get("imageinfo") or []
        if not infos:
            continue
        info = infos[0]
        mime = str(info.get("mime") or "")
        if not mime.startswith("image/"):
            continue
        meta = info.get("extmetadata") or {}

        def _meta(field: str) -> str | None:
            entry = meta.get(field)
            return str(entry.get("value")) if isinstance(entry, dict) and "value" in entry else None

        mapped = map_license(_meta("License") or _meta("LicenseShortName"))
        if mapped is None or mapped not in allowed_licenses:
            continue

        download_url = str(info.get("url") or "")
        if not download_url:
            continue
        title = str(page.get("title") or "").removeprefix("File:").strip() or None
        creator = _strip_html(_meta("Artist")) or _strip_html(_meta("Credit"))
        page_url = str(info.get("descriptionurl") or download_url)

        out.append(
            Candidate(
                download_url=download_url,
                page_url=page_url,
                title=title,
                creator=creator,
                license=mapped,
            )
        )
    return out


class WikimediaAdapter:
    """Fetches search results from Commons and yields collectable candidates."""

    name = "wikimedia"

    def candidates(self, source: SourceConfig, fetcher: Fetcher) -> list[Candidate]:
        allowed = set(source.allowed_licenses)
        seen: set[str] = set()
        found: list[Candidate] = []
        for query in source.queries:
            url = build_search_url(query, source.max_items)
            resp = fetcher.get(url)
            import json

            payload = json.loads(resp.body.decode("utf-8", errors="replace"))
            for cand in parse_candidates(payload, allowed):
                if cand.download_url in seen:
                    continue
                seen.add(cand.download_url)
                found.append(cand)
                if len(found) >= source.max_items:
                    return found
        return found
