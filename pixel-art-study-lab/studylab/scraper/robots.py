"""robots.txt compliance.

A tiny cache around :class:`urllib.robotparser.RobotFileParser`. Before any URL is fetched, the
runner asks :meth:`RobotsCache.can_fetch`; a source whose robots.txt disallows our path is skipped.
The fetch of robots.txt itself is injectable so the whole rule is testable offline.

Fail-closed: if robots.txt cannot be retrieved or parsed, we treat the path as *disallowed* rather
than assume permission.
"""

from __future__ import annotations

from typing import Callable
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

from studylab.logging_setup import get_logger

log = get_logger("robots")

#: A callable that returns the text of a robots.txt given its URL (or None if unavailable).
RobotsFetcher = Callable[[str], "str | None"]


def _default_fetcher(url: str, user_agent: str, timeout: float = 10.0) -> str | None:
    import urllib.request

    req = urllib.request.Request(url, headers={"User-Agent": user_agent})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 — http(s) only, below
            if resp.status != 200:
                return None
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read(512_000).decode(charset, errors="replace")
    except Exception as exc:  # noqa: BLE001 — any failure means "no robots.txt available"
        log.warning("could not fetch robots.txt %s: %s", url, exc)
        return None


class RobotsCache:
    """Caches robots.txt per host and answers can_fetch questions for a fixed user agent."""

    def __init__(self, user_agent: str, fetcher: RobotsFetcher | None = None) -> None:
        self.user_agent = user_agent
        self._fetcher = fetcher or (lambda url: _default_fetcher(url, user_agent))
        self._parsers: dict[str, RobotFileParser | None] = {}

    def _parser_for(self, url: str) -> RobotFileParser | None:
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https") or not parts.netloc:
            return None
        host_key = f"{parts.scheme}://{parts.netloc}"
        if host_key not in self._parsers:
            robots_url = f"{host_key}/robots.txt"
            text = self._fetcher(robots_url)
            if text is None:
                self._parsers[host_key] = None
            else:
                parser = RobotFileParser()
                parser.parse(text.splitlines())
                self._parsers[host_key] = parser
        return self._parsers[host_key]

    def can_fetch(self, url: str) -> bool:
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https"):
            return False  # only ever fetch over http(s)
        parser = self._parser_for(url)
        if parser is None:
            # No usable robots.txt → fail closed.
            log.info("no usable robots.txt for %s — treating as disallowed", url)
            return False
        return parser.can_fetch(self.user_agent, url)
