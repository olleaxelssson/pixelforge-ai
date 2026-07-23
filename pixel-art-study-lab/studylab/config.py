"""Configuration: filesystem layout and environment-driven settings.

Everything lives under a single data directory (``STUDYLAB_DATA_DIR``, default ``~/.studylab``)
so the whole library is easy to back up or delete. Secrets (API keys) are read from the
environment only — never stored in the database or on disk.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

# License identifiers we consider safe to *collect and reuse* for study.
# Everything else is refused by the scraper and flagged on import.
ALLOWED_LICENSES: frozenset[str] = frozenset(
    {
        "CC0-1.0",
        "PD",  # public domain
        "CC-BY-4.0",
        "CC-BY-3.0",
        "CC-BY-SA-4.0",
        "CC-BY-SA-3.0",
        "OGA-BY-3.0",  # OpenGameArt attribution
        "self",  # files the user added themselves
    }
)

# Licenses that require visible attribution when displayed.
ATTRIBUTION_REQUIRED: frozenset[str] = frozenset(
    {"CC-BY-4.0", "CC-BY-3.0", "CC-BY-SA-4.0", "CC-BY-SA-3.0", "OGA-BY-3.0"}
)

DEFAULT_USER_AGENT = (
    "PixelArtStudyLab/0.1 (+https://example.local/study-lab; personal research; respects robots.txt)"
)


def _env_path(name: str, default: Path) -> Path:
    raw = os.environ.get(name)
    return Path(raw).expanduser() if raw else default


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    #: Optional API key for stronger vision-language analysis (local mode works without it).
    vlm_api_key: str | None
    vlm_provider: str  # "local" (default) | "anthropic" | "openai"
    user_agent: str

    @property
    def db_path(self) -> Path:
        return self.data_dir / "studylab.db"

    @property
    def assets_dir(self) -> Path:
        return self.data_dir / "assets"

    @property
    def thumbs_dir(self) -> Path:
        return self.data_dir / "thumbnails"

    @property
    def log_path(self) -> Path:
        return self.data_dir / "studylab.log"

    def ensure_dirs(self) -> None:
        for path in (self.data_dir, self.assets_dir, self.thumbs_dir):
            path.mkdir(parents=True, exist_ok=True)


def load_settings() -> Settings:
    data_dir = _env_path("STUDYLAB_DATA_DIR", Path.home() / ".studylab")
    provider = os.environ.get("STUDYLAB_VLM_PROVIDER", "local").strip().lower()
    # Keys are read from the environment on demand and never persisted.
    key = os.environ.get("STUDYLAB_VLM_API_KEY") or None
    ua = os.environ.get("STUDYLAB_USER_AGENT", DEFAULT_USER_AGENT)
    return Settings(data_dir=data_dir, vlm_api_key=key, vlm_provider=provider, user_agent=ua)
