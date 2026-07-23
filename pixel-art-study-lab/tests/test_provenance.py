"""Provenance and licensing rules."""

from __future__ import annotations

import pytest

from studylab.provenance import (
    ProvenanceError,
    build_attribution,
    is_allowed_license,
    needs_attribution,
    require_collectable,
)


def test_allowlist_membership() -> None:
    assert is_allowed_license("CC0-1.0")
    assert is_allowed_license("self")
    assert not is_allowed_license("CC-BY-NC-4.0")
    assert not is_allowed_license("All Rights Reserved")


def test_attribution_requirement() -> None:
    assert needs_attribution("CC-BY-4.0")
    assert needs_attribution("CC-BY-SA-3.0")
    assert not needs_attribution("CC0-1.0")
    assert not needs_attribution("PD")


def test_build_attribution_default_and_template() -> None:
    default = build_attribution(
        license="CC-BY-4.0", creator="Jane", title="Hero", source_url="https://x/y"
    )
    assert "Jane" in default and "Hero" in default and "CC-BY-4.0" in default

    templated = build_attribution(
        license="CC0-1.0", creator=None, title="Tile", source_url="https://z",
        template="{title} ({license})",
    )
    assert templated == "Tile (CC0-1.0)"


def test_require_collectable_gate() -> None:
    require_collectable("CC0-1.0")  # no raise
    with pytest.raises(ProvenanceError):
        require_collectable("CC-BY-NC-4.0")
