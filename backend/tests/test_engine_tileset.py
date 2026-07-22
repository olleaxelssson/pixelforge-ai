"""Godot / Tiled tileset exporter tests (M24, D-001) — validated by parsing the output back."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image

from pixelforge.exporters.base import ExportAsset, ExportOptions
from pixelforge.exporters.godot_tileset import GodotTilesetExporter
from pixelforge.exporters.registry import get_exporter, list_exporters
from pixelforge.exporters.tiled_tileset import TiledTilesetExporter, _grid_mask, _wangid
from pixelforge.exporters.wang_blob import NE, SE, E, N, S, blob_masks


def _base() -> Image.Image:
    return Image.new("RGBA", (32, 32), (120, 180, 90, 255))


def _export(exporter, tmp_path: Path, name: str = "grass") -> list[Path]:
    return exporter.export(ExportAsset(frames=[_base()]), ExportOptions(base_name=name), tmp_path)


# --- Godot .tres -----------------------------------------------------------


def test_godot_tres_declares_47_tiles(tmp_path: Path) -> None:
    paths = _export(GodotTilesetExporter(), tmp_path)
    assert {p.name for p in paths} == {"grass_blob.png", "grass.tres"}
    tres = (tmp_path / "grass.tres").read_text()
    tiles = re.findall(r"^(\d+):(\d+)/0 = 0$", tres, re.M)
    assert len(tiles) == 47
    assert 'path="res://grass_blob.png"' in tres
    assert "texture_region_size = Vector2i(32, 32)" in tres
    assert "terrain_set_0/mode = 0" in tres
    assert 'sources/0 = SubResource("TileSetAtlasSource_0")' in tres


def test_godot_peering_bits_match_mask(tmp_path: Path) -> None:
    tres = tmp_path / "grass.tres"
    _export(GodotTilesetExporter(), tmp_path)
    text = tres.read_text()
    # Group the peering-bit lines by their tile coordinate.
    per_tile: dict[str, int] = {}
    for coord in re.findall(r"^(\d+:\d+)/0/terrains_peering_bit/\w+ = 0$", text, re.M):
        per_tile[coord] = per_tile.get(coord, 0) + 1
    # Each tile emits exactly one peering bit per set neighbour bit (popcount of its mask).
    masks = blob_masks()
    columns = 8
    for index, mask in enumerate(masks):
        coord = f"{index % columns}:{index // columns}"
        assert per_tile.get(coord, 0) == bin(mask).count("1")


# --- Tiled .tsx / .tmx -----------------------------------------------------


def test_tiled_tsx_wangset(tmp_path: Path) -> None:
    paths = _export(TiledTilesetExporter(), tmp_path)
    assert {p.name for p in paths} == {"grass_blob.png", "grass.tsx", "grass.tmx"}
    root = ET.parse(tmp_path / "grass.tsx").getroot()
    assert root.get("tilecount") == "47"
    assert root.find("image").get("source") == "grass_blob.png"
    wangtiles = root.findall(".//wangtile")
    assert len(wangtiles) == 47
    # Every wangid is 8 comma-separated 0/1 values.
    for wt in wangtiles:
        parts = wt.get("wangid").split(",")
        assert len(parts) == 8
        assert set(parts) <= {"0", "1"}


def test_tiled_wangid_encoding() -> None:
    assert _wangid(0) == "0,0,0,0,0,0,0,0"
    assert _wangid(255) == "1,1,1,1,1,1,1,1"
    # order is (N, NE, E, SE, S, SW, W, NW); N+S set → positions 0 and 4.
    assert _wangid(N | S) == "1,0,0,0,1,0,0,0"


def test_tiled_tmx_is_a_valid_map(tmp_path: Path) -> None:
    _export(TiledTilesetExporter(), tmp_path)
    root = ET.parse(tmp_path / "grass.tmx").getroot()
    assert root.get("width") == "4"
    assert root.find("tileset").get("source") == "grass.tsx"
    data = root.find(".//layer/data").text
    gids = [int(g) for g in re.findall(r"\d+", data)]
    assert len(gids) == 16  # 4×4
    assert all(1 <= g <= 47 for g in gids)  # valid tile GIDs (firstgid 1)


def test_grid_mask_corner_and_center() -> None:
    # Top-left cell of a patch: only S and E neighbours are inside → plus the SE corner.
    assert _grid_mask(0, 0, 4) == (S | E | SE)
    # An interior cell (1,1) of a 4×4 patch has all 8 neighbours.
    assert _grid_mask(1, 1, 4) == 255
    # A corner mask must not set a corner bit without both its edges (canonical by construction).
    assert not (_grid_mask(0, 0, 4) & NE)  # no north neighbour → no NE


# --- registry --------------------------------------------------------------


def test_engine_exporters_registered() -> None:
    assert get_exporter("godot-tileset").format_id == "godot-tileset"
    assert get_exporter("tiled-tileset").format_id == "tiled-tileset"
    ids = {e["format_id"] for e in list_exporters()}
    assert {"godot-tileset", "tiled-tileset"} <= ids
