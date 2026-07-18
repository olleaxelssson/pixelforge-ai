# Writing PixelForge Plugins (D-014)

A PixelForge plugin is an ordinary pip-installable Python package. It declares components in
`pixelforge.*` entry point groups plus one required **manifest**; the loader discovers, validates,
and registers everything at startup. The core always works with zero plugins installed.

## Quick start

See the working sample: [`examples/plugins/pixelforge-hello`](../../examples/plugins/pixelforge-hello).

```bash
pip install -e examples/plugins/pixelforge-hello
export PIXELFORGE_PLUGINS_ENABLED=true
export PIXELFORGE_PLUGIN_ALLOWLIST='["pixelforge-hello"]'
pixelforge list plugins          # shows loaded/skipped plugins with reasons
pixelforge export sprite.png --format ascii -o out/   # the plugin's exporter, like any builtin
```

## Entry point groups

| Group | Interface to implement | Registered into |
|---|---|---|
| `pixelforge.manifest` | `pixelforge.plugins.manifest.PluginManifest` (**required**, exactly one) | — |
| `pixelforge.exporters` | `pixelforge.exporters.base.Exporter` | exporter registry (`--format <id>`) |
| `pixelforge.qa_detectors` | `pixelforge.qa.detectors.base.Detector` | QA engine's default detector set |
| `pixelforge.agents` | `pixelforge.agents.base.Agent` | planning runtime's default agent set |
| `pixelforge.generation_backends` | `pixelforge.generation.backends.base.GenerationBackend` | Stage-A backend registry |
| `pixelforge.planning_backends` | `pixelforge.agents.planning_backends.base.PlanningBackend` | planning-backend registry |
| `pixelforge.embedding_backends` | `pixelforge.memory.embeddings.EmbeddingBackend` | identity-embedding registry |

An entry point may resolve to an **instance**, a **class**, or a **zero-argument factory**; the
loader normalizes all three and type-checks the result against the group's interface. Future groups
(palette analyzers, animation modules, prompt optimizers) arrive with their subsystems.

## The manifest

```python
from pixelforge.plugins.manifest import PluginManifest

MANIFEST = PluginManifest(
    name="my-plugin",
    version="0.1.0",
    author="You",
    description="What it adds",
    api_version="1.0",              # plugin-API version you target (see below)
    capabilities=["filesystem"],    # declare what you touch: filesystem, network, ...
)
```

## Versioning

The plugin API is semver `major.minor` (`pixelforge.plugins.manifest.PLUGIN_API_VERSION`, currently
`1.0`). Rules: a plugin whose `api_version` **major** differs from the core's is refused; a newer
**minor** loads with a warning. Interface-breaking changes to the tables above only happen with a
major bump and a deprecation cycle.

## Trust model — read this

Plugins run **in-process with full Python privileges**, exactly like any dependency you install.
PixelForge therefore:

- ships with plugins **disabled** (`plugins_enabled=false`);
- loads only distributions on the explicit **allowlist** (`plugin_allowlist`);
- logs every load, and isolates failures (a broken plugin is skipped, never crashes the app);
- surfaces the result at `GET /api/plugins` and `pixelforge list plugins`.

Only allowlist plugins you trust as much as your other dependencies. Declare honest `capabilities`
in your manifest; sandboxed execution for untrusted plugins is a future tier (see ADR D-014).

## Environment configuration

```bash
PIXELFORGE_PLUGINS_ENABLED=true
PIXELFORGE_PLUGIN_ALLOWLIST='["pixelforge-hello","my-other-plugin"]'   # JSON list
```

## Testing your plugin

The loader's discovery is injectable, so you can test without installing:

```python
from pixelforge.plugins.loader import DiscoveredEntry, load_plugins, reset_plugin_state

entries = [
    DiscoveredEntry("my-plugin", "0.1.0", "pixelforge.manifest", "manifest", lambda: MANIFEST),
    DiscoveredEntry("my-plugin", "0.1.0", "pixelforge.exporters", "fmt", lambda: MyExporter),
]
reset_plugin_state()
report = load_plugins(settings, discover=lambda: entries)
```

See `backend/tests/test_plugins.py` for full patterns (allowlist, version mismatch, broken
components).
