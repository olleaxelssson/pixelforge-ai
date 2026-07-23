"""Direct-URL adapter.

For a hand-curated list of image URLs whose license the maintainer already knows (e.g. a page of
CC0 tilesets you vetted yourself). Each URL becomes a candidate carrying the source's single declared
license. Because the license is asserted by whoever edits ``sources.toml``, ``direct`` sources should
list exactly one entry in ``allowed_licenses`` — the license that applies to every URL.
"""

from __future__ import annotations

from studylab.scraper.fetch import Fetcher
from studylab.scraper.models import Candidate, SourceConfig


class DirectAdapter:
    """Yields one candidate per configured URL, all under the source's declared license."""

    name = "direct"

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
                    creator=None,
                    license=license,
                )
            )
        return out
