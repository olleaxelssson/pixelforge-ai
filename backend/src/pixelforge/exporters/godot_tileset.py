"""Godot 4 TileSet exporter (M24, D-001): a drop-in ``.tres`` terrain autotiler.

Emits the 47-tile blob sheet plus a Godot 4 ``TileSet`` text resource: one ``TileSetAtlasSource``
over the sheet, and — for every tile — the terrain-set/peering-bit metadata derived from the blob
bitmask. Each set neighbour bit becomes the Godot peering bit for that direction, so Godot's
"match corners and sides" terrain autotiling picks the right tile with no hand-editing. Pure and
deterministic; the ``.tres`` is plain text validated by parsing it back.
"""

from __future__ import annotations

from pathlib import Path

from pixelforge.exporters.base import ExportAsset, Exporter, ExportOptions
from pixelforge.exporters.wang_blob import (
    NE,
    NW,
    SE,
    SW,
    BlobSheet,
    E,
    N,
    S,
    W,
    build_blob_sheet,
)

# Blob neighbour bit → Godot 4 peering-bit name (TERRAIN_MODE_MATCH_CORNERS_AND_SIDES).
_PEERING = {
    N: "top_side",
    NE: "top_right_corner",
    E: "right_side",
    SE: "bottom_right_corner",
    S: "bottom_side",
    SW: "bottom_left_corner",
    W: "left_side",
    NW: "top_left_corner",
}
# Match-corners-and-sides mode enum value on Godot's TileSet.
_TERRAIN_MODE_CORNERS_AND_SIDES = 0


class GodotTilesetExporter(Exporter):
    format_id = "godot-tileset"
    display_name = "Godot 4 TileSet (.tres)"

    def export(self, asset: ExportAsset, options: ExportOptions, dest: Path) -> list[Path]:
        sheet = build_blob_sheet(
            asset.scaled_frames(options.scale), columns=options.columns or 8, padding=0
        )
        png_name = f"{options.base_name}_blob.png"
        sheet.image.save(dest / png_name)

        tres_path = dest / f"{options.base_name}.tres"
        tres_path.write_text(_build_tres(sheet, png_name, options.base_name))
        return [dest / png_name, tres_path]


def _build_tres(sheet: BlobSheet, png_name: str, name: str) -> str:
    atlas_id = "TileSetAtlasSource_0"
    tex_id = "1_tex"
    lines = [
        '[gd_resource type="TileSet" load_steps=3 format=3]',
        "",
        f'[ext_resource type="Texture2D" path="res://{png_name}" id="{tex_id}"]',
        "",
        f'[sub_resource type="TileSetAtlasSource" id="{atlas_id}"]',
        f'texture = ExtResource("{tex_id}")',
        f"texture_region_size = Vector2i({sheet.tile_width}, {sheet.tile_height})",
    ]
    for cell in sheet.cells:
        tile = f"{cell.col}:{cell.row}/0"
        lines.append(f"{tile} = 0")
        lines.append(f"{tile}/terrain_set = 0")
        lines.append(f"{tile}/terrain = 0")
        for bit, peering in _PEERING.items():
            if cell.mask & bit:
                lines.append(f"{tile}/terrains_peering_bit/{peering} = 0")
    lines += [
        "",
        "[resource]",
        f"tile_size = Vector2i({sheet.tile_width}, {sheet.tile_height})",
        f"terrain_set_0/mode = {_TERRAIN_MODE_CORNERS_AND_SIDES}",
        f'terrain_set_0/terrain_0/name = "{name}"',
        "terrain_set_0/terrain_0/color = Color(0.5, 0.6, 0.4, 1)",
        f'sources/0 = SubResource("{atlas_id}")',
        "",
    ]
    return "\n".join(lines)
