"""Critique of an uploaded sprite, grounded in general technique + the licensed reference library.

Compares the upload's metrics against healthy ranges (optionally learned from the user's own
licensed references of a similar size) and returns concrete, teachable suggestions — never a
prescription to copy any specific artwork.
"""

from __future__ import annotations

from typing import Any

# Sensible defaults if the library has no comparable references yet.
_DEFAULTS = {"palette_median": 16, "contrast_median": 0.45, "coverage_median": 0.4}


def critique(analysis: dict[str, Any], ref_stats: dict[str, float] | None = None) -> dict[str, Any]:
    ref = {**_DEFAULTS, **(ref_stats or {})}
    palette = analysis["palette"]
    pa = analysis["pixel_art"]
    strengths: list[str] = []
    suggestions: list[str] = []

    n = palette["color_count"]
    if n > max(64, ref["palette_median"] * 3):
        suggestions.append(
            f"Palette is large ({n} colours) vs ~{int(ref['palette_median'])} typical for this "
            "size in your library — reducing it usually sharpens shapes and reads better small."
        )
    elif n <= 32:
        strengths.append(f"Economical palette ({n} colours).")

    if palette["contrast_range"] < 0.25 and n > 1:
        suggestions.append(
            "Low value contrast — add clearly darker and lighter steps so forms don't blend."
        )
    else:
        strengths.append("Readable value contrast.")

    if pa["silhouette_coverage"] < 0.9 and pa["silhouette_compactness"] >= 0.5:
        strengths.append("Clear, compact silhouette.")
    elif pa["silhouette_compactness"] < 0.35 and pa["silhouette_coverage"] < 0.9:
        suggestions.append(
            "Scattered silhouette — tighten the shape or remove stray pixels so it reads as one form."
        )

    if pa["outline_ratio"] < 0.15 and pa["transparent_ratio"] > 0.1:
        suggestions.append(
            "No consistent outline — a darker edge (selective or full) often improves readability "
            "against varied backgrounds."
        )
    elif pa["outline_ratio"] >= 0.3:
        strengths.append("Consistent outline.")

    if pa["flatness"] < 0.4 and n > 64:
        suggestions.append(
            "Lots of single-pixel colour changes (noise) — flatten large areas and reserve detail "
            "for edges and focal points."
        )

    if pa["grid_scale"] > 1:
        suggestions.append(
            f"Image is upscaled ×{pa['grid_scale']}; edit at the logical "
            f"{pa['effective_width']}×{pa['effective_height']} to keep pixels crisp."
        )

    if not suggestions:
        suggestions.append("Solid fundamentals — no major issues detected by the local analysis.")

    return {
        "strengths": strengths,
        "suggestions": suggestions,
        "compared_against": ref,
    }
