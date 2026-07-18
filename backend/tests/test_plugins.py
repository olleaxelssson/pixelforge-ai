"""Plugin SDK tests (D-014): loader, trust model, isolation, and the sample plugin end to end.

Discovery is injected, so no packages are installed; global registries are snapshotted and restored
around every test so plugin components never leak into other test files.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from pixelforge.agents import registry as agents_registry
from pixelforge.agents.planning_backends import registry as planning_registry
from pixelforge.config import Settings
from pixelforge.exporters import registry as exporters_registry
from pixelforge.exporters.base import ExportAsset, Exporter, ExportOptions
from pixelforge.memory import embeddings as embeddings_module
from pixelforge.plugins.loader import DiscoveredEntry, load_plugins, reset_plugin_state
from pixelforge.plugins.manifest import PluginManifest
from pixelforge.qa import registry as qa_registry
from pixelforge.qa.models import DetectorContext

_SAMPLE_SRC = Path(__file__).parents[2] / "examples" / "plugins" / "pixelforge-hello" / "src"


@pytest.fixture(autouse=True)
def _isolated_registries():
    """Snapshot every plugin-mutable registry and the loader cache; restore after each test."""
    exporters_registry._ensure_registered()
    snapshots = (
        dict(exporters_registry._EXPORTERS),
        list(agents_registry._PLUGIN_AGENTS),
        list(qa_registry._PLUGIN_DETECTORS),
        dict(planning_registry._BACKENDS),
        dict(embeddings_module._BACKENDS),
    )
    reset_plugin_state()
    yield
    exporters_registry._EXPORTERS.clear()
    exporters_registry._EXPORTERS.update(snapshots[0])
    agents_registry._PLUGIN_AGENTS[:] = snapshots[1]
    qa_registry._PLUGIN_DETECTORS[:] = snapshots[2]
    planning_registry._BACKENDS.clear()
    planning_registry._BACKENDS.update(snapshots[3])
    embeddings_module._BACKENDS.clear()
    embeddings_module._BACKENDS.update(snapshots[4])
    reset_plugin_state()


def _settings(**overrides) -> Settings:
    return Settings(**overrides)


class _TxtExporter(Exporter):
    format_id = "plugin-txt"
    display_name = "Plugin TXT"

    def export(self, asset: ExportAsset, options: ExportOptions, dest: Path) -> list[Path]:
        path = dest / f"{options.base_name}.txt"
        path.write_text(f"{len(asset.frames)} frame(s)\n")
        return [path]


def _manifest(name: str = "demo-plugin", api_version: str = "1.0") -> PluginManifest:
    return PluginManifest(name=name, version="0.1.0", api_version=api_version)


def _entries(
    dist: str = "demo-plugin", api_version: str = "1.0", extra: list[DiscoveredEntry] | None = None
) -> list[DiscoveredEntry]:
    base = [
        DiscoveredEntry(
            dist, "0.1.0", "pixelforge.manifest", "manifest", lambda: _manifest(dist, api_version)
        ),
        DiscoveredEntry(dist, "0.1.0", "pixelforge.exporters", "txt", lambda: _TxtExporter),
    ]
    return base + (extra or [])


# --- trust model ------------------------------------------------------------


def test_disabled_by_default_loads_nothing() -> None:
    report = load_plugins(_settings(), discover=lambda: _entries())
    assert report.enabled is False and report.loaded == [] and report.skipped == []


def test_not_on_allowlist_is_skipped() -> None:
    settings = _settings(plugins_enabled=True, plugin_allowlist=[])
    report = load_plugins(settings, discover=lambda: _entries())
    assert report.loaded == []
    assert report.skipped[0].reason == "not in plugin_allowlist"


def test_allowlisted_plugin_registers_components() -> None:
    settings = _settings(plugins_enabled=True, plugin_allowlist=["demo-plugin"])
    report = load_plugins(settings, discover=lambda: _entries())
    assert [p.name for p in report.loaded] == ["demo-plugin"]
    assert report.loaded[0].components == ["pixelforge.exporters:txt"]
    assert exporters_registry.get_exporter("plugin-txt").display_name == "Plugin TXT"


# --- validation & isolation -------------------------------------------------


def test_missing_manifest_is_skipped() -> None:
    entries = [e for e in _entries() if e.group != "pixelforge.manifest"]
    settings = _settings(plugins_enabled=True, plugin_allowlist=["demo-plugin"])
    report = load_plugins(settings, discover=lambda: entries)
    assert report.loaded == [] and "no manifest" in report.skipped[0].reason


def test_api_major_mismatch_is_refused() -> None:
    settings = _settings(plugins_enabled=True, plugin_allowlist=["demo-plugin"])
    report = load_plugins(settings, discover=lambda: _entries(api_version="2.0"))
    assert report.loaded == [] and "incompatible" in report.skipped[0].reason


def test_broken_component_is_isolated_not_fatal() -> None:
    def explode() -> object:
        raise RuntimeError("boom")

    entries = _entries(
        extra=[DiscoveredEntry("demo-plugin", "0.1.0", "pixelforge.agents", "bad", explode)]
    )
    settings = _settings(plugins_enabled=True, plugin_allowlist=["demo-plugin"])
    report = load_plugins(settings, discover=lambda: entries)
    plugin = report.loaded[0]
    assert plugin.components == ["pixelforge.exporters:txt"]
    assert any("boom" in error for error in plugin.errors)


def test_wrong_interface_is_rejected() -> None:
    entries = [
        DiscoveredEntry("demo-plugin", "0.1.0", "pixelforge.manifest", "m", _manifest),
        DiscoveredEntry("demo-plugin", "0.1.0", "pixelforge.qa_detectors", "x", lambda: object()),
    ]
    settings = _settings(plugins_enabled=True, plugin_allowlist=["demo-plugin"])
    report = load_plugins(settings, discover=lambda: entries)
    assert report.loaded == []  # its only component failed -> whole plugin skipped
    assert "all components failed" in report.skipped[0].reason


def test_load_is_idempotent() -> None:
    settings = _settings(plugins_enabled=True, plugin_allowlist=["demo-plugin"])
    first = load_plugins(settings, discover=lambda: _entries())
    second = load_plugins(settings, discover=lambda: [])  # different discovery is ignored
    assert second is first


# --- sample plugin end to end -----------------------------------------------


def _sample_entries() -> list[DiscoveredEntry]:
    sys.path.insert(0, str(_SAMPLE_SRC))
    try:
        import pixelforge_hello
    finally:
        sys.path.pop(0)
    dist = "pixelforge-hello"
    return [
        DiscoveredEntry(
            dist, "0.1.0", "pixelforge.manifest", "manifest", lambda: pixelforge_hello.MANIFEST
        ),
        DiscoveredEntry(
            dist,
            "0.1.0",
            "pixelforge.exporters",
            "ascii",
            lambda: pixelforge_hello.AsciiArtExporter,
        ),
        DiscoveredEntry(
            dist,
            "0.1.0",
            "pixelforge.qa_detectors",
            "checkerboard",
            lambda: pixelforge_hello.CheckerboardDetector,
        ),
    ]


def test_sample_plugin_loads_and_works(tmp_path) -> None:
    settings = _settings(plugins_enabled=True, plugin_allowlist=["pixelforge-hello"])
    report = load_plugins(settings, discover=_sample_entries)
    assert len(report.loaded) == 1 and len(report.loaded[0].components) == 2

    # The exporter behaves like any builtin.
    frame = Image.new("RGBA", (4, 4), (255, 255, 255, 255))
    paths = exporters_registry.get_exporter("ascii").export(
        ExportAsset(frames=[frame]), ExportOptions(base_name="s"), tmp_path
    )
    assert paths[0].read_text().splitlines()[0] == "@@@@"

    # The detector joins the QA default set: fires on checkerboard, silent on flat sprites.
    detector = qa_registry.DetectorRegistry().get("checkerboard-noise")
    checker = np.zeros((8, 8, 4), np.uint8)
    checker[..., 3] = 255
    checker[::2, ::2, 0] = 255
    checker[1::2, 1::2, 0] = 255
    checker[::2, 1::2, 1] = 255
    checker[1::2, ::2, 1] = 255
    assert detector.detect(checker, DetectorContext())
    flat = np.zeros((8, 8, 4), np.uint8)
    flat[..., 0], flat[..., 3] = 200, 255
    assert detector.detect(flat, DetectorContext()) == []


# --- API + CLI --------------------------------------------------------------


def test_plugins_endpoint_reports_disabled(client) -> None:
    response = client.get("/api/plugins")
    assert response.status_code == 200
    assert response.json()["enabled"] is False


def test_cli_list_plugins(capsys) -> None:
    from pixelforge.cli import main

    assert main(["list", "plugins"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["enabled"] is False and payload["api_version"] == "1.0"
