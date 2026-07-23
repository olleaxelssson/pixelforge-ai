"""Provenance and licensing: what we may collect, and how to attribute it.

Every asset must carry a license drawn from :data:`config.ALLOWED_LICENSES`. Attribution strings are
built once at import time so the UI can always display credit without re-deriving it.
"""

from __future__ import annotations

from studylab.config import ALLOWED_LICENSES, ATTRIBUTION_REQUIRED


class ProvenanceError(ValueError):
    """Raised when an asset's license/provenance is not acceptable for collection."""


def is_allowed_license(license: str) -> bool:
    return license in ALLOWED_LICENSES


def needs_attribution(license: str) -> bool:
    return license in ATTRIBUTION_REQUIRED


def build_attribution(
    *,
    license: str,
    creator: str | None,
    title: str | None,
    source_url: str | None,
    template: str | None = None,
) -> str:
    """A ready-to-display credit line. Templates use {creator}/{title}/{source_url}/{license}."""
    creator = creator or "Unknown"
    title = title or "Untitled"
    if template:
        return template.format(
            creator=creator, title=title, source_url=source_url or "", license=license
        )
    parts = [f'"{title}"', f"by {creator}"]
    if source_url:
        parts.append(f"({source_url})")
    parts.append(f"— {license}")
    return " ".join(parts)


def require_collectable(license: str) -> None:
    """Raise if this license may not be collected (used by the scraper, not local imports)."""
    if not is_allowed_license(license):
        raise ProvenanceError(
            f"license '{license}' is not in the allowlist "
            f"({', '.join(sorted(ALLOWED_LICENSES))}); refusing to collect."
        )
