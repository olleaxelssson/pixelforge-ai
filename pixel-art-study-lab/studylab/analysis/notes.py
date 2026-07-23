"""Explainable study notes: *why* a sprite reads the way it does — never a copy of it.

Turns the numeric analysis into short, teachable observations grounded in general pixel-art
technique (palette economy, silhouette, outlines, value contrast, dithering, tileability).
"""

from __future__ import annotations

from typing import Any


def study_notes(analysis: dict[str, Any]) -> dict[str, Any]:
    palette = analysis["palette"]
    pa = analysis["pixel_art"]
    notes: list[str] = []

    n = palette["color_count"]
    if n <= 4:
        notes.append(f"Extremely tight palette ({n} colours) — every colour does heavy lifting.")
    elif n <= 16:
        notes.append(f"Tight palette ({n} colours) keeps shapes legible and reads at small sizes.")
    elif n <= 64:
        notes.append(f"Moderate palette ({n} colours) — room for shading ramps without noise.")
    else:
        notes.append(
            f"Large palette ({n} colours) — unusual for hand-made pixel art; may be upscaled, "
            "photographic, or heavily dithered."
        )

    cov = pa["silhouette_coverage"]
    comp = pa["silhouette_compactness"]
    if cov < 0.9 and comp >= 0.5:
        notes.append(
            f"Strong silhouette ({int(cov * 100)}% coverage, compact) — the shape is recognisable "
            "from its outline alone."
        )
    elif cov >= 0.9:
        notes.append("Fills the frame — little negative space, so the silhouette does less work.")
    else:
        notes.append("Sparse/scattered silhouette — the eye has to work harder to read the shape.")

    if pa["outline_ratio"] >= 0.3:
        notes.append("A dark outline separates the sprite from the background at small sizes.")
    if palette["contrast_range"] >= 0.4:
        notes.append("Good value contrast across the palette — light and shadow read clearly.")
    elif palette["contrast_range"] < 0.2 and n > 1:
        notes.append("Low value contrast — forms risk blending together; add darker/lighter steps.")
    if pa["dithering"] >= 0.03:
        notes.append("Uses dithering to fake extra shades/gradients from a limited palette.")
    if len(palette["ramps"]) >= 1:
        notes.append(
            f"Has {len(palette['ramps'])} shading ramp(s) — deliberate light→dark colour steps."
        )
    if pa["tileable_h"] >= 0.92 and pa["tileable_v"] >= 0.92:
        notes.append("Tiles seamlessly in both directions — suitable as a repeating texture.")
    elif pa["tileable_h"] >= 0.92 or pa["tileable_v"] >= 0.92:
        notes.append("Tiles seamlessly in one direction only.")
    if pa["grid_scale"] > 1:
        notes.append(
            f"Stored upscaled ×{pa['grid_scale']}; the logical art is "
            f"{pa['effective_width']}×{pa['effective_height']}."
        )

    reads_at = f"{pa['effective_width']}×{pa['effective_height']}"
    return {"reads_at": reads_at, "notes": notes}
