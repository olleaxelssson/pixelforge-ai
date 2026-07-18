"""Plugin loader (D-014): discover entry points, validate, and register components.

Discovery walks installed distributions for ``pixelforge.*`` entry point groups. A distribution is
loaded only when plugins are enabled AND its name is on the explicit allowlist; it must ship a
manifest whose plugin-API major version matches the core's. Every failure — bad manifest, version
mismatch, a component that raises on import — is logged and isolated; the app never crashes because
of a plugin. Loading is idempotent: repeated calls return the first run's report.

The discovery function is injectable so the loader is fully testable without installing packages.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from importlib import metadata

from pixelforge.agents.base import Agent
from pixelforge.agents.planning_backends.base import PlanningBackend
from pixelforge.agents.planning_backends.registry import register_planning_backend
from pixelforge.agents.registry import register_agent
from pixelforge.config import Settings
from pixelforge.exporters.base import Exporter
from pixelforge.exporters.registry import register_exporter
from pixelforge.generation.backends.base import GenerationBackend
from pixelforge.generation.backends.registry import register_backend
from pixelforge.memory.embeddings import EmbeddingBackend, register_embedding_backend
from pixelforge.plugins.manifest import (
    PLUGIN_API_VERSION,
    LoadedPlugin,
    PluginManifest,
    PluginReport,
    SkippedPlugin,
)
from pixelforge.qa.detectors.base import Detector
from pixelforge.qa.registry import register_detector

logger = logging.getLogger("pixelforge.plugins")

MANIFEST_GROUP = "pixelforge.manifest"


@dataclass
class DiscoveredEntry:
    """One entry point found in an installed distribution (or injected by tests)."""

    dist_name: str
    dist_version: str
    group: str
    name: str
    load: Callable[[], object]


def _register_component(group: str, obj: object) -> None:
    """Validate the resolved object against the group's interface and register it."""
    if group == "pixelforge.agents":
        _expect(obj, Agent, group)
        register_agent(obj)  # type: ignore[arg-type]
    elif group == "pixelforge.exporters":
        _expect(obj, Exporter, group)
        register_exporter(obj)  # type: ignore[arg-type]
    elif group == "pixelforge.qa_detectors":
        _expect(obj, Detector, group)
        register_detector(obj)  # type: ignore[arg-type]
    elif group == "pixelforge.generation_backends":
        _expect(obj, GenerationBackend, group)
        register_backend(obj)  # type: ignore[arg-type]
    elif group == "pixelforge.planning_backends":
        _expect(obj, PlanningBackend, group)
        register_planning_backend(lambda instance=obj: instance)  # type: ignore[misc, return-value]
    elif group == "pixelforge.embedding_backends":
        _expect(obj, EmbeddingBackend, group)
        register_embedding_backend(lambda instance=obj: instance)  # type: ignore[misc, return-value]
    else:  # pragma: no cover - guarded by COMPONENT_GROUPS
        raise ValueError(f"unknown entry point group: {group}")


COMPONENT_GROUPS: tuple[str, ...] = (
    "pixelforge.agents",
    "pixelforge.exporters",
    "pixelforge.qa_detectors",
    "pixelforge.generation_backends",
    "pixelforge.planning_backends",
    "pixelforge.embedding_backends",
)

_report: PluginReport | None = None


def _expect(obj: object, base: type, group: str) -> None:
    if not isinstance(obj, base):
        raise TypeError(f"{group} entry resolved to {type(obj).__name__}, expected {base.__name__}")


def _resolve(loaded: object) -> object:
    """Entry points may point at an instance, a class, or a zero-argument factory."""
    if isinstance(loaded, type) or callable(loaded):
        candidate = loaded() if isinstance(loaded, type) else loaded
        if callable(candidate) and not _is_component(candidate):
            candidate = candidate()
        return candidate
    return loaded


def _is_component(obj: object) -> bool:
    bases = (Agent, Exporter, Detector, GenerationBackend, PlanningBackend, EmbeddingBackend)
    return isinstance(obj, bases)


def discover_installed() -> list[DiscoveredEntry]:
    """Walk installed distributions for pixelforge entry point groups (stdlib only)."""
    wanted = {MANIFEST_GROUP, *COMPONENT_GROUPS}
    found: list[DiscoveredEntry] = []
    for dist in metadata.distributions():
        dist_name = dist.name or ""
        for entry in dist.entry_points:
            if entry.group in wanted:
                found.append(
                    DiscoveredEntry(
                        dist_name=dist_name,
                        dist_version=dist.version or "0.0.0",
                        group=entry.group,
                        name=entry.name,
                        load=entry.load,
                    )
                )
    return found


def _compatible(api_version: str) -> tuple[bool, str]:
    try:
        plugin_major, plugin_minor = (int(x) for x in api_version.split(".")[:2])
        core_major, core_minor = (int(x) for x in PLUGIN_API_VERSION.split(".")[:2])
    except ValueError:
        return False, f"unparsable api_version {api_version!r}"
    if plugin_major != core_major:
        return False, f"api_version {api_version} incompatible with core {PLUGIN_API_VERSION}"
    if plugin_minor > core_minor:
        logger.warning(
            "plugin targets newer plugin-API minor (%s > %s); loading anyway",
            api_version,
            PLUGIN_API_VERSION,
        )
    return True, ""


def _load_manifest(entries: list[DiscoveredEntry]) -> PluginManifest:
    manifest_entries = [e for e in entries if e.group == MANIFEST_GROUP]
    if not manifest_entries:
        raise ValueError("no manifest (expected an entry point in group 'pixelforge.manifest')")
    loaded = manifest_entries[0].load()
    if isinstance(loaded, PluginManifest):
        return loaded
    if isinstance(loaded, dict):
        return PluginManifest.model_validate(loaded)
    raise TypeError(f"manifest resolved to {type(loaded).__name__}, expected PluginManifest")


def _load_distribution(dist_name: str, entries: list[DiscoveredEntry]) -> LoadedPlugin:
    manifest = _load_manifest(entries)
    ok, reason = _compatible(manifest.api_version)
    if not ok:
        raise ValueError(reason)

    plugin = LoadedPlugin(
        name=dist_name, version=entries[0].dist_version, manifest=manifest, components=[]
    )
    for entry in entries:
        if entry.group == MANIFEST_GROUP:
            continue
        try:
            _register_component(entry.group, _resolve(entry.load()))
            plugin.components.append(f"{entry.group}:{entry.name}")
        except Exception as error:  # noqa: BLE001 - isolate per component
            message = f"{entry.group}:{entry.name} failed: {error}"
            logger.warning("plugin %s component %s", dist_name, message)
            plugin.errors.append(message)
    if not plugin.components and plugin.errors:
        raise ValueError(f"all components failed to load: {'; '.join(plugin.errors)}")
    return plugin


def load_plugins(
    settings: Settings,
    discover: Callable[[], Iterable[DiscoveredEntry]] = discover_installed,
) -> PluginReport:
    """Discover, validate, and register plugins once; later calls return the first report."""
    global _report
    if _report is not None:
        return _report

    if not settings.plugins_enabled:
        _report = PluginReport(enabled=False)
        return _report

    report = PluginReport(enabled=True)
    by_dist: dict[str, list[DiscoveredEntry]] = {}
    for entry in discover():
        by_dist.setdefault(entry.dist_name, []).append(entry)

    allowlist = set(settings.plugin_allowlist)
    for dist_name, entries in sorted(by_dist.items()):
        if dist_name not in allowlist:
            report.skipped.append(SkippedPlugin(name=dist_name, reason="not in plugin_allowlist"))
            continue
        try:
            plugin = _load_distribution(dist_name, entries)
        except Exception as error:  # noqa: BLE001 - a bad plugin must never crash the app
            logger.warning("skipping plugin %s: %s", dist_name, error)
            report.skipped.append(SkippedPlugin(name=dist_name, reason=str(error)))
            continue
        logger.info("loaded plugin %s %s (%s)", dist_name, plugin.version, plugin.components)
        report.loaded.append(plugin)

    _report = report
    return report


def reset_plugin_state() -> None:
    """Testing hook: forget the cached report so the next ``load_plugins`` runs discovery again."""
    global _report
    _report = None
