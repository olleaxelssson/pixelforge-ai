"""Controlled, rules-first collection. Nothing is fetched unless a source is explicitly enabled in
the allowlist, its robots.txt permits it, its license is on the allowlist, and per-domain rate
limits are respected. Default runs are dry-runs."""
