import json

from PIL import Image

from pixelforge.exporters.base import ExportAsset, ExportOptions
from pixelforge.exporters.registry import get_exporter, list_exporters


def _asset(frame_count=4, size=16):
    frames = [
        Image.new("RGBA", (size, size), (i * 40 % 256, 100, 150, 255)) for i in range(frame_count)
    ]
    return ExportAsset(frames=frames)


def test_registry_lists_all_formats():
    ids = {e["format_id"] for e in list_exporters()}
    assert ids >= {"png", "gif", "sprite-sheet", "texture-atlas", "unity", "godot", "unreal"}


def test_png_export_scaled(tmp_path):
    paths = get_exporter("png").export(_asset(1), ExportOptions(scale=4), tmp_path)
    assert len(paths) == 1
    assert Image.open(paths[0]).size == (64, 64)


def test_gif_export(tmp_path):
    paths = get_exporter("gif").export(_asset(), ExportOptions(), tmp_path)
    gif = Image.open(paths[0])
    assert gif.format == "GIF"
    assert gif.n_frames == 4


def test_sprite_sheet_layout(tmp_path):
    paths = get_exporter("sprite-sheet").export(_asset(4), ExportOptions(columns=2), tmp_path)
    sheet = Image.open(paths[0])
    assert sheet.size == (32, 32)


def test_texture_atlas_metadata(tmp_path):
    paths = get_exporter("texture-atlas").export(_asset(4), ExportOptions(), tmp_path)
    atlas = json.loads(next(p for p in paths if p.suffix == ".json").read_text())
    assert len(atlas["frames"]) == 4
    assert atlas["meta"]["size"]["w"] == 64


def test_unity_export_meta(tmp_path):
    paths = get_exporter("unity").export(_asset(2), ExportOptions(base_name="hero"), tmp_path)
    meta = next(p for p in paths if p.name.endswith(".meta")).read_text()
    assert "filterMode: 0" in meta
    assert "hero_1" in meta


def test_godot_export_tres(tmp_path):
    paths = get_exporter("godot").export(_asset(2), ExportOptions(base_name="hero"), tmp_path)
    tres = next(p for p in paths if p.suffix == ".tres").read_text()
    assert 'type="SpriteFrames"' in tres
    assert "Rect2(16, 0, 16, 16)" in tres


def test_unreal_export_pow2(tmp_path):
    paths = get_exporter("unreal").export(_asset(3), ExportOptions(), tmp_path)
    sheet = Image.open(next(p for p in paths if p.suffix == ".png"))
    assert sheet.size == (64, 16)  # 48 -> padded to 64
    meta = json.loads(next(p for p in paths if p.suffix == ".json").read_text())
    assert len(meta["frames"]) == 3
