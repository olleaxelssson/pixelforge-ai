# D-014: Agent / Tool Plugin SDK

- **Status:** Accepted — implemented M12 (loader, manifest, six entry-point groups, allowlist trust
  model, sample plugin). Future tiers (frontend slots, subprocess/WASM isolation) remain open.
- **Date:** 2026-07-16
- **Deciders:** Agentic architecture review (Claude Code)
- **Related:** generalizes the existing registries (D-005) and the `GenerationBackend`/`Exporter`
  interfaces; extension points defined by D-009–D-013; realizes the ROADMAP M6 "Plugin API" and the
  "plugin marketplace architecture" deliverable.

## Context

PixelForge already lets you add models, styles, palettes, and exporters via registries and data
files. The brief wants third parties to add **new AI agents, painting tools, prompt optimizers,
exporters, tile generators, animation modules, palette analyzers, and training pipelines** *without
modifying core code*. That requires (a) stable, documented extension interfaces and (b) a discovery
mechanism so external packages plug in at runtime.

## Decision

**1. Standard Python entry points** (`importlib.metadata`) layered over the registry pattern. A
plugin is an ordinary pip-installable package that declares entry points in named groups:

```
[project.entry-points."pixelforge.agents"]      my_agent = my_pkg.agents:MyAgent
[project.entry-points."pixelforge.tools"]        my_tool = my_pkg.tools:my_tool
[project.entry-points."pixelforge.exporters"]    my_exp  = my_pkg.exporters:MyExporter
[project.entry-points."pixelforge.palette_analyzers"] ...
[project.entry-points."pixelforge.qa_detectors"] ...
[project.entry-points."pixelforge.planning_backends"] ...
[project.entry-points."pixelforge.animation_modules"] ...
[project.entry-points."pixelforge.prompt_optimizers"] ...
```

**2. Stabilized extension interfaces** — the protocols/ABCs plugins implement, each already emerging
from another ADR: `GenerationBackend` (exists), `Exporter` (exists), `PlanningBackend` (D-010),
`Agent` (D-010), `Tool` (D-010), `PaletteAnalyzer` (D-012), `Detector` (D-013), plus
`AnimationModule` and `PromptOptimizer`. These interfaces are **semantically versioned**; a plugin
declares the core API version it targets.

**3. A plugin loader** (`plugins/loader.py`) discovers entry points at startup, reads each plugin's
**manifest** (name, version, author, targeted API version, declared capabilities/permissions),
validates the API-version match (warn on mismatch, refuse on incompatible), and registers the plugin
into the corresponding registry. The core must work with **zero plugins** installed.

**4. Trust model, stated honestly.** Plugins are Python code running **in-process with full trust**,
exactly like any dependency — a real security consideration (named risk). Mitigations shipped now:
plugins are **disabled by default** and enabled explicitly (settings allowlist); the manifest
declares what a plugin touches; loading is logged. Mitigations noted as **future**: signature/
allowlist verification and optional **subprocess/WASM isolation** for untrusted plugins.

**5. Frontend extension slots** (panels, tools) are declared via a manifest the renderer consumes;
the detailed FE contract is deferred to its own ADR/impl and is not required for backend plugins.

## Alternatives considered

| Option | Verdict | Why |
|---|---|---|
| **A. Entry points + registries + manifest (chosen)** | **Chosen** | Python-standard discovery, no bespoke machinery, versioned, reuses packaging; plugins are normal packages. |
| **B. "Drop a `.py` in a folder"** | Rejected | Simple but no metadata, versioning, or dependency management; fragile at ecosystem scale. |
| **C. Bespoke manifest + directory scan + dynamic import** | Rejected | Reinvents packaging; entry points already solve discovery + metadata. |
| **D. Subprocess/WASM sandbox for all plugins now** | Deferred | Strong isolation but high complexity and perf cost; document as a future option, not the v1 default. |

## Cross-cutting analysis

- **Complexity:** Moderate, and mostly *discipline* rather than code: the hard part is **stabilizing
  and documenting interfaces** so they can be public. The loader itself is small.
- **Performance & budget:** Entry-point discovery happens once at startup (tens of ms for a handful
  of plugins). No steady-state cost. Lazy-load heavy plugins on first use.
- **Scalability:** Unbounded third-party ecosystem; underpins the "plugin marketplace" deliverable.
  Registries already scale to many entries.
- **Maintainability:** Forces clean, versioned public interfaces (good pressure on the whole
  codebase). Each extension point gets a documented contract + a sample plugin.
- **Licensing:** Discovery uses stdlib `importlib.metadata` (PSF) — no new dependency. **Core stays
  MIT.** Third-party plugins carry their own licenses; loading a GPL plugin at runtime does not
  relicense the MIT core, but *distributors* bundling GPL plugins must mind aggregation — documented
  in developer docs so we don't accidentally ship an incompatible bundle.
- **Security/privacy:** The central risk. In-process plugins can read the filesystem, hit the
  network, and see user data. Mitigations above (disabled-by-default, manifest, allowlist, future
  isolation). Cloud-calling plugins must declare it in the manifest.

## Benchmarks & validation plan

- **Sample plugin:** ship a minimal `examples/plugins/hello-exporter` (and a `hello-agent`) proving
  an external package registers via entry points end-to-end.
- **Loader tests:** discovery finds installed entry points; API-version mismatch warns/refuses as
  specified; a plugin raising at import is isolated (logged, skipped) without crashing the app.
- **Zero-plugin test:** the app and full test suite pass with no plugins installed.
- **Registration tests:** a loaded plugin's agent/exporter/detector actually appears in the relevant
  registry and is usable through the normal code paths.

## Repo mapping

| Piece | Location |
|---|---|
| Loader + manifest | new `plugins/loader.py`, `plugins/manifest.py` |
| Extension-point registration hooks | each subsystem exposes `register()` (agents, exporters, qa, palettes, planning backends) |
| Entry-point groups | documented in developer docs; consumed by the loader |
| Sample plugins | `examples/plugins/` |
| Settings | plugin allowlist / enable flags in `config/settings.py` |
| Docs | new `docs/developer/plugins.md` (contracts, versioning, security) |

## Implementation notes (M12)

Shipped as designed, with these concrete choices:

- **Entry-point groups (six + manifest):** `pixelforge.manifest` (required, exactly one) plus
  `pixelforge.agents`, `pixelforge.exporters`, `pixelforge.qa_detectors`,
  `pixelforge.generation_backends`, `pixelforge.planning_backends`, `pixelforge.embedding_backends`.
  The remaining groups from the design table (`tools`, `palette_analyzers`, `animation_modules`,
  `prompt_optimizers`) arrive with their subsystems — the loader is table-driven, so adding a group
  is one `COMPONENT_GROUPS` entry plus one `_register_component` branch.
- **Manifest & versioning:** `PluginManifest` (pydantic) carries `name/version/author/description/
  api_version/capabilities`. `PLUGIN_API_VERSION = "1.0"`; a plugin whose **major** differs is
  refused, a newer **minor** loads with a warning.
- **Trust model:** `plugins_enabled=false` by default; a distribution loads only when enabled AND on
  the `plugin_allowlist`. Entry points may resolve to an instance, a class, or a zero-arg factory;
  each is normalized and `isinstance`-checked against the group interface. Per-component failures are
  isolated (logged, recorded in the plugin's `errors`); a distribution whose components all fail is
  skipped whole. Loading is idempotent (cached report).
- **Surfaces:** `GET /api/plugins` and `pixelforge list plugins` return the `PluginReport`
  (enabled, api_version, loaded, skipped-with-reasons). Discovery is injectable, so the loader is
  tested with no packages installed; the sample `examples/plugins/pixelforge-hello` proves the real
  entry-point path (ASCII-art exporter + checkerboard-noise detector).

## Consequences & open questions

- **Positive:** third parties extend every subsystem without forking; forces durable public APIs;
  enables the marketplace vision; core stays MIT and plugin-free by default.
- **Negative:** interface stability becomes a hard commitment (breaking changes need deprecation
  cycles); in-process trust is a real security surface until isolation lands.
- **Open:** (1) Timing — land this **after** D-009–D-013 interfaces have stabilized (premature
  freezing is worse than none). (2) Isolation roadmap — evaluate subprocess vs. WASM for an
  "untrusted plugin" tier. (3) Frontend extension-slot contract — its own ADR when the editor depth
  milestone (M5) firms up.
