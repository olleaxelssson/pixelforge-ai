"""Load and validate the source allowlist (``sources.toml``).

Nothing here fetches anything. This module turns a human-edited TOML file into validated
:class:`SourceConfig` objects and *refuses* configurations that would violate the project's rules:

* ``obey_robots`` may not be turned off — a ``false`` value is rejected outright.
* every entry in a source's ``allowed_licenses`` must be on :data:`config.ALLOWED_LICENSES`.
* a source must name a known adapter and a positive, sane rate limit.

A source is only ever collected from when it is explicitly ``enabled = true``; the default is off.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from studylab.config import ALLOWED_LICENSES
from studylab.scraper.models import SourceConfig

KNOWN_ADAPTERS = frozenset({"wikimedia", "direct"})


class AllowlistError(ValueError):
    """Raised when ``sources.toml`` is malformed or breaks a collection rule."""


def _validate(cfg: SourceConfig) -> SourceConfig:
    if cfg.adapter not in KNOWN_ADAPTERS:
        raise AllowlistError(
            f"source '{cfg.name}': unknown adapter '{cfg.adapter}' "
            f"(known: {', '.join(sorted(KNOWN_ADAPTERS))})"
        )
    if cfg.obey_robots is not True:
        raise AllowlistError(
            f"source '{cfg.name}': obey_robots must be true — refusing to disable robots.txt "
            "compliance."
        )
    if cfg.rate_limit_per_sec <= 0 or cfg.rate_limit_per_sec > 10:
        raise AllowlistError(
            f"source '{cfg.name}': rate_limit_per_sec must be in (0, 10]; got "
            f"{cfg.rate_limit_per_sec}."
        )
    if cfg.max_items <= 0:
        raise AllowlistError(f"source '{cfg.name}': max_items must be positive.")
    bad = sorted(set(cfg.allowed_licenses) - ALLOWED_LICENSES)
    if bad:
        raise AllowlistError(
            f"source '{cfg.name}': licenses {bad} are not on the allowlist "
            f"({', '.join(sorted(ALLOWED_LICENSES))})."
        )
    if not cfg.allowed_licenses:
        raise AllowlistError(
            f"source '{cfg.name}': allowed_licenses is empty — list at least one permitted license."
        )
    # A completeness check that only matters once a source is actually turned on — a disabled
    # template (e.g. sources.example.toml with its URLs commented out) must still load.
    if cfg.enabled and cfg.adapter == "direct" and not cfg.urls:
        raise AllowlistError(f"source '{cfg.name}': the 'direct' adapter needs at least one url.")
    return cfg


def _source_from_table(name: str, table: dict[str, object]) -> SourceConfig:
    def _get(key: str, default: object) -> object:
        return table.get(key, default)

    try:
        cfg = SourceConfig(
            name=name,
            adapter=str(_get("adapter", "")),
            enabled=bool(_get("enabled", False)),
            homepage=str(_get("homepage", "")),
            terms_url=str(_get("terms_url", "")),
            rate_limit_per_sec=float(_get("rate_limit_per_sec", 0.5)),  # type: ignore[arg-type]
            max_items=int(_get("max_items", 40)),  # type: ignore[arg-type]
            allowed_licenses=[str(x) for x in _get("allowed_licenses", [])],  # type: ignore[union-attr]
            queries=[str(x) for x in _get("queries", [])],  # type: ignore[union-attr]
            urls=[str(x) for x in _get("urls", [])],  # type: ignore[union-attr]
            attribution_template=(
                str(table["attribution_template"]) if "attribution_template" in table else None
            ),
            obey_robots=bool(_get("obey_robots", True)),
        )
    except (TypeError, ValueError) as exc:
        raise AllowlistError(f"source '{name}': malformed field — {exc}") from exc
    return _validate(cfg)


def parse_allowlist(text: str) -> list[SourceConfig]:
    """Parse TOML text into validated sources. Every ``[sources.<name>]`` table is one source."""
    data = tomllib.loads(text)
    raw = data.get("sources", {})
    if not isinstance(raw, dict):
        raise AllowlistError("top-level 'sources' must be a table of named sources.")
    sources = [_source_from_table(name, table) for name, table in raw.items()]  # type: ignore[arg-type]
    names = [s.name for s in sources]
    dupes = {n for n in names if names.count(n) > 1}
    if dupes:
        raise AllowlistError(f"duplicate source names: {', '.join(sorted(dupes))}")
    return sources


def load_allowlist(path: Path) -> list[SourceConfig]:
    """Read and validate ``sources.toml``. Missing file → empty list (nothing enabled)."""
    if not path.exists():
        return []
    return parse_allowlist(path.read_text(encoding="utf-8"))


def enabled_sources(sources: list[SourceConfig]) -> list[SourceConfig]:
    return [s for s in sources if s.enabled]


def find_source(sources: list[SourceConfig], name: str) -> SourceConfig | None:
    for s in sources:
        if s.name == name:
            return s
    return None
