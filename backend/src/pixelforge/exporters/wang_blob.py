"""Wang / blob auto-tile sheet exporter (M22, D-001).

Builds the standard **47-tile "blob" set** from a single base tile plus edge/corner carving — the
tileset a game engine indexes by a bitmask of its 8 neighbours to auto-tile terrain. The 47 comes
from the blob rule: a *corner* neighbour only matters when **both** of its adjacent *edge*
neighbours are also present, which collapses the 256 raw 8-bit configurations down to 47 distinct
tiles. Each tile is rendered by carving a border band off every disconnected side of the base tile
and rounding the inner corners, so the result is fully deterministic. A JSON sidecar maps every
neighbour bitmask to its cell, so the sheet is directly usable for auto-tiling.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image

from pixelforge.exporters.base import ExportAsset, Exporter, ExportOptions

# Edge bits (orthogonal neighbours) and corner bits (diagonal neighbours).
N, E, S, W = 1, 2, 4, 8
NE, SE, SW, NW = 16, 32, 64, 128
# Each corner and the two edges that must both be present for it to count.
_CORNERS = {NE: (N, E), SE: (S, E), SW: (S, W), NW: (N, W)}
_DEFAULT_COLUMNS = 8


def _canonical(mask: int) -> int:
    """Zero out any corner bit whose two adjacent edges are not both set (the blob rule)."""
    for corner, (edge_a, edge_b) in _CORNERS.items():
        if not (mask & edge_a and mask & edge_b):
            mask &= ~corner
    return mask


def blob_masks() -> list[int]:
    """The 47 canonical neighbour bitmasks of the blob tileset, in ascending order."""
    return sorted({_canonical(m) for m in range(256)})


def _render_tile(base: np.ndarray, mask: int, band: int) -> np.ndarray:
    """Carve the base tile down to the shape implied by ``mask`` (disconnected sides removed)."""
    tile = base.copy()
    if not mask & N:
        tile[:band, :] = 0
    if not mask & S:
        tile[-band:, :] = 0
    if not mask & W:
        tile[:, :band] = 0
    if not mask & E:
        tile[:, -band:] = 0
    # Round inner corners: both adjacent edges present, but the diagonal neighbour is not.
    if mask & N and mask & E and not mask & NE:
        tile[:band, -band:] = 0
    if mask & S and mask & E and not mask & SE:
        tile[-band:, -band:] = 0
    if mask & S and mask & W and not mask & SW:
        tile[-band:, :band] = 0
    if mask & N and mask & W and not mask & NW:
        tile[:band, :band] = 0
    return tile


class WangBlobExporter(Exporter):
    format_id = "wang-blob"
    display_name = "Wang/Blob Auto-Tile Sheet (47)"

    def export(self, asset: ExportAsset, options: ExportOptions, dest: Path) -> list[Path]:
        base_img = asset.scaled_frames(options.scale)[0].convert("RGBA")
        base = np.asarray(base_img, dtype=np.uint8)
        height, width = base.shape[:2]
        band = max(1, min(width, height) // 4)

        masks = blob_masks()
        columns = options.columns or _DEFAULT_COLUMNS
        rows = (len(masks) + columns - 1) // columns
        pad = options.padding
        cell_w, cell_h = width + pad, height + pad
        sheet = Image.new("RGBA", (columns * cell_w - pad, rows * cell_h - pad), (0, 0, 0, 0))

        mapping = []
        for index, mask in enumerate(masks):
            col, row = index % columns, index // columns
            x, y = col * cell_w, row * cell_h
            tile = _render_tile(base, mask, band)
            sheet.paste(Image.fromarray(tile, "RGBA"), (x, y))
            mapping.append(
                {
                    "mask": mask,
                    "index": index,
                    "x": x,
                    "y": y,
                    "neighbors": {
                        "n": bool(mask & N),
                        "e": bool(mask & E),
                        "s": bool(mask & S),
                        "w": bool(mask & W),
                        "ne": bool(mask & NE),
                        "se": bool(mask & SE),
                        "sw": bool(mask & SW),
                        "nw": bool(mask & NW),
                    },
                }
            )

        sheet_path = dest / f"{options.base_name}_blob.png"
        sheet.save(sheet_path)
        meta = {
            "meta": {
                "image": sheet_path.name,
                "tile": {"w": width, "h": height},
                "tiles": len(masks),
            },
            "bits": {"n": N, "e": E, "s": S, "w": W, "ne": NE, "se": SE, "sw": SW, "nw": NW},
            "tiles": mapping,
        }
        json_path = dest / f"{options.base_name}_blob.json"
        json_path.write_text(json.dumps(meta, indent=2))
        return [sheet_path, json_path]
