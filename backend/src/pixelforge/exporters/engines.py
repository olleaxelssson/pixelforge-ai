"""Game-engine-oriented exporters: Unity, Godot, Unreal."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from pixelforge.animation.assembly import build_sprite_sheet
from pixelforge.exporters.base import ExportAsset, Exporter, ExportOptions


class UnityExporter(Exporter):
    """Sprite sheet + .meta file preconfigured for pixel-perfect Unity import
    (point filtering, no compression, multiple sprite mode with slices)."""

    format_id = "unity"
    display_name = "Unity-ready"

    def export(self, asset: ExportAsset, options: ExportOptions, dest: Path) -> list[Path]:
        frames = asset.scaled_frames(options.scale)
        cols = options.columns or len(frames)
        sheet = build_sprite_sheet(frames, columns=cols, padding=options.padding)
        sheet_path = dest / f"{options.base_name}.png"
        sheet.save(sheet_path)

        fw, fh = frames[0].size
        sprites = "\n".join(
            f"""    - serializedVersion: 2
      name: {options.base_name}_{i}
      rect:
        serializedVersion: 2
        x: {(i % cols) * (fw + options.padding)}
        y: {sheet.height - ((i // cols) + 1) * fh - (i // cols) * options.padding}
        width: {fw}
        height: {fh}
      alignment: 0
      pivot: {{x: 0.5, y: 0.5}}"""
            for i in range(len(frames))
        )
        meta = f"""fileFormatVersion: 2
guid: {uuid.uuid4().hex}
TextureImporter:
  textureType: 8
  spriteMode: 2
  spritePixelsToUnits: {fh}
  filterMode: 0
  textureCompression: 0
  mipmaps:
    enableMipMap: 0
  spriteSheet:
    sprites:
{sprites}
"""
        meta_path = dest / f"{options.base_name}.png.meta"
        meta_path.write_text(meta)
        return [sheet_path, meta_path]


class GodotExporter(Exporter):
    """Sprite sheet + SpriteFrames .tres resource for AnimatedSprite2D."""

    format_id = "godot"
    display_name = "Godot-ready"

    def export(self, asset: ExportAsset, options: ExportOptions, dest: Path) -> list[Path]:
        frames = asset.scaled_frames(options.scale)
        cols = options.columns or len(frames)
        sheet = build_sprite_sheet(frames, columns=cols, padding=options.padding)
        sheet_path = dest / f"{options.base_name}.png"
        sheet.save(sheet_path)

        fw, fh = frames[0].size
        atlas_blocks = []
        frame_refs = []
        for i in range(len(frames)):
            x = (i % cols) * (fw + options.padding)
            y = (i // cols) * (fh + options.padding)
            atlas_blocks.append(
                f'[sub_resource type="AtlasTexture" id="Atlas_{i}"]\n'
                f'atlas = ExtResource("1")\n'
                f"region = Rect2({x}, {y}, {fw}, {fh})\n"
            )
            frame_refs.append(f'{{\n"duration": 1.0,\n"texture": SubResource("Atlas_{i}")\n}}')
        fps = round(1000.0 / max(options.frame_duration_ms, 1), 2)
        tres = (
            f'[gd_resource type="SpriteFrames" load_steps={len(frames) + 2} format=3]\n\n'
            f'[ext_resource type="Texture2D" path="res://{sheet_path.name}" id="1"]\n\n'
            + "\n".join(atlas_blocks)
            + "\n[resource]\nanimations = [{\n"
            + f'"frames": [{", ".join(frame_refs)}],\n'
            + f'"loop": true,\n"name": &"{options.base_name}",\n"speed": {fps}\n}}]\n'
        )
        tres_path = dest / f"{options.base_name}_frames.tres"
        tres_path.write_text(tres)
        return [sheet_path, tres_path]


class UnrealExporter(Exporter):
    """Power-of-two padded sheet + Paper2D-friendly JSON metadata."""

    format_id = "unreal"
    display_name = "Unreal-ready"

    def export(self, asset: ExportAsset, options: ExportOptions, dest: Path) -> list[Path]:
        frames = asset.scaled_frames(options.scale)
        cols = options.columns or len(frames)
        sheet = build_sprite_sheet(frames, columns=cols, padding=options.padding)

        padded_w = _next_pow2(sheet.width)
        padded_h = _next_pow2(sheet.height)
        if (padded_w, padded_h) != sheet.size:
            from PIL import Image

            padded = Image.new("RGBA", (padded_w, padded_h), (0, 0, 0, 0))
            padded.paste(sheet, (0, 0))
            sheet = padded

        sheet_path = dest / f"{options.base_name}_T.png"
        sheet.save(sheet_path)

        fw, fh = frames[0].size
        meta = {
            "texture": sheet_path.name,
            "textureSize": {"w": sheet.width, "h": sheet.height},
            "importSettings": {"filter": "nearest", "compression": "UserInterface2D"},
            "frames": [
                {
                    "name": f"{options.base_name}_{i}",
                    "x": (i % cols) * (fw + options.padding),
                    "y": (i // cols) * (fh + options.padding),
                    "w": fw,
                    "h": fh,
                }
                for i in range(len(frames))
            ],
            "frameRate": round(1000.0 / max(options.frame_duration_ms, 1), 2),
        }
        json_path = dest / f"{options.base_name}_flipbook.json"
        json_path.write_text(json.dumps(meta, indent=2))
        return [sheet_path, json_path]


def _next_pow2(value: int) -> int:
    result = 1
    while result < value:
        result *= 2
    return result
