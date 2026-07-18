"""Plugin manifest and load-report models (D-014).

Every plugin distribution must expose one entry point in the ``pixelforge.manifest`` group that
resolves to a :class:`PluginManifest`. The manifest names the plugin, targets a plugin-API version,
and declares what the plugin touches — the honest, in-process trust model the ADR describes.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

#: The core's plugin-API version (semver ``major.minor``). Same major → compatible; a plugin
#: targeting a newer minor than the core loads with a warning; a different major is refused.
PLUGIN_API_VERSION = "1.0"


class PluginManifest(BaseModel):
    name: str
    version: str = "0.0.0"
    author: str = ""
    description: str = ""
    api_version: str  # plugin-API version this plugin targets, e.g. "1.0"
    capabilities: list[str] = Field(default_factory=list)  # e.g. ["network", "filesystem"]


class LoadedPlugin(BaseModel):
    name: str  # distribution name
    version: str
    manifest: PluginManifest
    components: list[str] = Field(default_factory=list)  # "group:entry_name"
    errors: list[str] = Field(default_factory=list)  # per-component failures (isolated)


class SkippedPlugin(BaseModel):
    name: str
    reason: str


class PluginReport(BaseModel):
    enabled: bool
    api_version: str = PLUGIN_API_VERSION
    loaded: list[LoadedPlugin] = Field(default_factory=list)
    skipped: list[SkippedPlugin] = Field(default_factory=list)
