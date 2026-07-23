"""Rate-limited, retrying HTTP fetch — the only place the scraper touches the network.

Two concerns, kept separate so both are testable:

* :class:`RateLimiter` — a per-domain token spacing that enforces at most ``rate_per_sec`` requests.
* :class:`Fetcher` — the interface the runner depends on. :class:`HttpFetcher` is the real,
  urllib-based implementation (retries with exponential backoff); tests inject a fake instead, so no
  test ever hits the network.

Only ``http``/``https`` URLs are ever fetched, and only up to a size cap.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, Protocol
from urllib.parse import urlsplit

from studylab.logging_setup import get_logger

log = get_logger("fetch")

MAX_BYTES = 25 * 1024 * 1024  # 25 MiB safety cap per download


@dataclass
class FetchResponse:
    url: str
    status: int
    content_type: str
    body: bytes


class FetchError(RuntimeError):
    """A download failed after all retries (or was refused before it began)."""


class Fetcher(Protocol):
    """What the runner needs: fetch bytes for a URL, or raise :class:`FetchError`."""

    def get(self, url: str) -> FetchResponse: ...


@dataclass
class RateLimiter:
    """Spaces requests per host to at most ``rate_per_sec``. Shared clock is injectable for tests."""

    rate_per_sec: float
    monotonic: Callable[[], float] = time.monotonic
    sleep: Callable[[float], None] = time.sleep
    _next_allowed: dict[str, float] = field(default_factory=dict)

    def wait(self, url: str) -> None:
        if self.rate_per_sec <= 0:
            return
        host = urlsplit(url).netloc
        interval = 1.0 / self.rate_per_sec
        now = self.monotonic()
        earliest = self._next_allowed.get(host, 0.0)
        if now < earliest:
            self.sleep(earliest - now)
            now = earliest
        self._next_allowed[host] = now + interval


class HttpFetcher:
    """Real fetcher: urllib + exponential-backoff retries, guarded by a :class:`RateLimiter`."""

    def __init__(
        self,
        user_agent: str,
        rate_per_sec: float = 0.5,
        *,
        retries: int = 3,
        timeout: float = 20.0,
        limiter: RateLimiter | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.user_agent = user_agent
        self.retries = retries
        self.timeout = timeout
        self.limiter = limiter or RateLimiter(rate_per_sec)
        self._sleep = sleep

    def get(self, url: str) -> FetchResponse:
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https"):
            raise FetchError(f"refusing non-http(s) URL: {url}")

        self.limiter.wait(url)
        last_exc: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                return self._get_once(url)
            except Exception as exc:  # noqa: BLE001 — retry any transient failure
                last_exc = exc
                if attempt < self.retries:
                    backoff = 2.0**attempt
                    log.warning(
                        "fetch %s failed (attempt %d/%d): %s — retrying in %.0fs",
                        url,
                        attempt + 1,
                        self.retries + 1,
                        exc,
                        backoff,
                    )
                    self._sleep(backoff)
        raise FetchError(f"failed to fetch {url} after {self.retries + 1} attempts: {last_exc}")

    def _get_once(self, url: str) -> FetchResponse:
        import urllib.request

        req = urllib.request.Request(url, headers={"User-Agent": self.user_agent})
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:  # noqa: S310 — scheme checked
            status = getattr(resp, "status", 200) or 200
            if status != 200:
                raise FetchError(f"HTTP {status} for {url}")
            content_type = resp.headers.get_content_type()
            body = resp.read(MAX_BYTES + 1)
            if len(body) > MAX_BYTES:
                raise FetchError(f"response exceeds {MAX_BYTES} bytes: {url}")
            return FetchResponse(url=url, status=status, content_type=content_type, body=body)
