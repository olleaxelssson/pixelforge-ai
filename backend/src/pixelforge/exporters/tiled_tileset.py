"""Tiled tileset exporter (M24, D-001): a drop-in ``.tsx`` + sample ``.tmx``.

Emits the 47-tile blob sheet, a Tiled ``.tsx`` tileset whose ``<wangset>`` encodes the terrain from
the blob bitmasks (one ``<wangtile>`` per tile, ``wangid`` in Tiled's top/top-right/…/top-left
order), and a small ``.tmx`` sample map that auto-tiles a solid terrain patch so the wangset is
demonstrable on open. Pure, deterministic XML — validated by parsing it back with ElementTree.
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
    blob_masks,
    build_blob_sheet,
)

_SAMPLE = 4  # sample-map side length in tiles
_TILED_VERSION = "1.10"
_TILED_APP_VERSION = "1.10.2"


def _wangid(mask: int) -> str:
    """Tiled ``wangid``: 8 colours, top / top-right / … / top-left order (0 unset, 1 terrain)."""
    order = (N, NE, E, SE, S, SW, W, NW)
    return ",".join("1" if mask & bit else "0" for bit in order)


def _grid_mask(row: int, col: int, size: int) -> int:
    """The blob mask a cell needs inside a solid ``size`` × ``size`` terrain patch."""
    north, south = row > 0, row < size - 1
    west, east = col > 0, col < size - 1
    mask = 0
    mask |= N if north else 0
    mask |= S if south else 0
    mask |= W if west else 0
    mask |= E if east else 0
    # A corner only counts when both its adjacent edges are inside the patch (the blob rule).
    mask |= NE if north and east else 0
    mask |= SE if south and east else 0
    mask |= SW if south and west else 0
    mask |= NW if north and west else 0
    return mask


class TiledTilesetExporter(Exporter):
    format_id = "tiled-tileset"
    display_name = "Tiled Tileset (.tsx + .tmx)"

    def export(self, asset: ExportAsset, options: ExportOptions, dest: Path) -> list[Path]:
        sheet = build_blob_sheet(
            asset.scaled_frames(options.scale), columns=options.columns or 8, padding=0
        )
        png_name = f"{options.base_name}_blob.png"
        sheet.image.save(dest / png_name)

        tsx_name = f"{options.base_name}.tsx"
        tsx_path = dest / tsx_name
        tsx_path.write_text(_build_tsx(sheet, png_name, options.base_name))

        tmx_path = dest / f"{options.base_name}.tmx"
        tmx_path.write_text(_build_tmx(sheet, tsx_name))
        return [dest / png_name, tsx_path, tmx_path]


def _build_tsx(sheet: BlobSheet, png_name: str, name: str) -> str:
    tile_count = len(sheet.cells)
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<tileset version="{_TILED_VERSION}" tiledversion="{_TILED_APP_VERSION}" name="{name}" '
        f'tilewidth="{sheet.tile_width}" tileheight="{sheet.tile_height}" '
        f'tilecount="{tile_count}" columns="{sheet.columns}">',
        f' <image source="{png_name}" width="{sheet.image.width}" height="{sheet.image.height}"/>',
        " <wangsets>",
        f'  <wangset name="{name}" type="mixed" tile="-1">',
        f'   <wangcolor name="{name}" color="#d08040" tile="-1" probability="1"/>',
    ]
    for cell in sheet.cells:
        lines.append(f'   <wangtile tileid="{cell.index}" wangid="{_wangid(cell.mask)}"/>')
    lines += ["  </wangset>", " </wangsets>", "</tileset>", ""]
    return "\n".join(lines)


def _build_tmx(sheet: BlobSheet, tsx_name: str) -> str:
    masks = blob_masks()
    index_of = {mask: i for i, mask in enumerate(masks)}
    rows = []
    for row in range(_SAMPLE):
        gids = [str(index_of[_grid_mask(row, col, _SAMPLE)] + 1) for col in range(_SAMPLE)]
        rows.append(",".join(gids))
    csv = ",\n".join(rows)
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<map version="{_TILED_VERSION}" tiledversion="{_TILED_APP_VERSION}" '
        f'orientation="orthogonal" renderorder="right-down" width="{_SAMPLE}" height="{_SAMPLE}" '
        f'tilewidth="{sheet.tile_width}" tileheight="{sheet.tile_height}" infinite="0" '
        'nextlayerid="2" nextobjectid="1">',
        f' <tileset firstgid="1" source="{tsx_name}"/>',
        f' <layer id="1" name="terrain" width="{_SAMPLE}" height="{_SAMPLE}">',
        '  <data encoding="csv">',
        csv,
        "</data>",
        " </layer>",
        "</map>",
        "",
    ]
    return "\n".join(lines)
