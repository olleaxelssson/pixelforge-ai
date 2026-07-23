"""LLM-facing digest: a compact, canonical, machine-optimal description of an asset.

The human-facing study notes live in ``notes.py``. This module emits a *second* representation
designed to be read by a language model (including this project's optional API vision mode, or an
assistant helping the user study): dense, unambiguous, deterministic, and token-efficient. Every
metric is normalised to a fixed range with an explicit key, so a model can parse it without prose.

Format (v1), one line of space-separated ``key=value`` tokens::

    PALAB/1 kind=pixel_art conf=0.82 grid=1 res=16x16 px=256 pal=8 contrast=0.55 sep=0.31
    sil.cov=0.42 sil.comp=0.61 outline=0.44 dither=0.00 ramps=2 tile.h=0.31 tile.v=0.28
    frames=1 anim=0 sheet=0 alpha=1 transp=0.58 license=CC0-1.0 pal_hex=#1a1c2c,#5d275d,...
    | tags: knight,armor | notes: tight palette; strong silhouette; dark outline
"""

from __future__ import annotations

from typing import Any

VERSION = "PALAB/1"


def build_digest(analysis: dict[str, Any], meta: dict[str, Any] | None = None) -> str:
    meta = meta or {}
    p = analysis["palette"]
    a = analysis["pixel_art"]
    f = analysis["frames"]
    tokens = [
        VERSION,
        f"kind={'pixel_art' if a['is_pixel_art'] else 'other'}",
        f"conf={a['confidence']:.2f}",
        f"grid={a['grid_scale']}",
        f"res={a['effective_width']}x{a['effective_height']}",
        f"px={a['effective_width'] * a['effective_height']}",
        f"pal={p['color_count']}",
        f"contrast={p['contrast_range']:.2f}",
        f"sep={p['min_separation']:.2f}",
        f"sil.cov={a['silhouette_coverage']:.2f}",
        f"sil.comp={a['silhouette_compactness']:.2f}",
        f"outline={a['outline_ratio']:.2f}",
        f"dither={a['dithering']:.2f}",
        f"ramps={len(p['ramps'])}",
        f"tile.h={a['tileable_h']:.2f}",
        f"tile.v={a['tileable_v']:.2f}",
        f"frames={f['frame_count']}",
        f"anim={int(f['is_animation'])}",
        f"sheet={int(f['is_sheet'])}",
        f"alpha={int(a['has_alpha'])}",
        f"transp={a['transparent_ratio']:.2f}",
    ]
    if meta.get("license"):
        tokens.append(f"license={meta['license']}")
    if p["hex"]:
        tokens.append("pal_hex=" + ",".join(p["hex"][:8]))

    line = " ".join(tokens)
    tags = meta.get("tags") or []
    if tags:
        line += " | tags: " + ",".join(tags)
    notes = analysis.get("notes", {}).get("notes", [])
    if notes:
        line += " | notes: " + "; ".join(s.rstrip(".").lower() for s in notes[:6])
    return line
