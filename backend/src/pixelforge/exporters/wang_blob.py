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
from dataclasses import dataclass
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


@dataclass(frozen=True)
class BlobCell:
    """One cell of the assembled blob sheet: which mask it holds and where it sits."""

    mask: int
    index: int
    col: int
    row: int
    x: int
    y: int


@dataclass(frozen=True)
class BlobSheet:
    """The assembled 47-tile sheet plus the metadata engine exporters need."""

    image: Image.Image
    cells: list[BlobCell]
    tile_width: int
    tile_height: int
    columns: int
    rows: int


def build_blob_sheet(
    frames: list[Image.Image], columns: int = _DEFAULT_COLUMNS, padding: int = 0
) -> BlobSheet:
    """Assemble the 47-tile blob sheet from one or more base tiles (variants are cycled).

    Shared by the PNG/JSON exporter and the Godot/Tiled engine exporters (M24) so all three read
    the *same* tile shapes and cell coordinates.
    """
    bases = [np.asarray(f.convert("RGBA"), dtype=np.uint8) for f in frames]
    height, width = bases[0].shape[:2]
    band = max(1, min(width, height) // 4)

    masks = blob_masks()
    rows = (len(masks) + columns - 1) // columns
    cell_w, cell_h = width + padding, height + padding
    image = Image.new("RGBA", (columns * cell_w - padding, rows * cell_h - padding), (0, 0, 0, 0))

    cells: list[BlobCell] = []
    for index, mask in enumerate(masks):
        col, row = index % columns, index // columns
        x, y = col * cell_w, row * cell_h
        tile = _render_tile(bases[index % len(bases)], mask, band)
        image.paste(Image.fromarray(tile, "RGBA"), (x, y))
        cells.append(BlobCell(mask=mask, index=index, col=col, row=row, x=x, y=y))
    return BlobSheet(
        image=image, cells=cells, tile_width=width, tile_height=height, columns=columns, rows=rows
    )


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
        # One base tile → one blob set. Multiple frames (M23 seam-locked variants, which share
        # edges) are cycled across the 47 cells so the sheet shows the whole terrain family.
        sheet = build_blob_sheet(
            asset.scaled_frames(options.scale),
            columns=options.columns or _DEFAULT_COLUMNS,
            padding=options.padding,
        )
        sheet_path = dest / f"{options.base_name}_blob.png"
        sheet.image.save(sheet_path)
        meta = {
            "meta": {
                "image": sheet_path.name,
                "tile": {"w": sheet.tile_width, "h": sheet.tile_height},
                "tiles": len(sheet.cells),
            },
            "bits": {"n": N, "e": E, "s": S, "w": W, "ne": NE, "se": SE, "sw": SW, "nw": NW},
            "tiles": [
                {
                    "mask": c.mask,
                    "index": c.index,
                    "x": c.x,
                    "y": c.y,
                    "neighbors": {
                        "n": bool(c.mask & N),
                        "e": bool(c.mask & E),
                        "s": bool(c.mask & S),
                        "w": bool(c.mask & W),
                        "ne": bool(c.mask & NE),
                        "se": bool(c.mask & SE),
                        "sw": bool(c.mask & SW),
                        "nw": bool(c.mask & NW),
                    },
                }
                for c in sheet.cells
            ],
        }
        json_path = dest / f"{options.base_name}_blob.json"
        json_path.write_text(json.dumps(meta, indent=2))
        return [sheet_path, json_path]
