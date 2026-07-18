"""Plugin SDK (D-014): third-party extensions via standard Python entry points.

A plugin is an ordinary pip-installable package that declares components in ``pixelforge.*`` entry
point groups plus a required manifest. Loading is **off by default** and gated by an explicit
allowlist (``plugins_enabled`` / ``plugin_allowlist``); a broken plugin is logged and skipped, never
crashing the app. The core works with zero plugins installed.
"""
