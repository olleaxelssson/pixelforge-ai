"""Standard exporters: PNG, GIF, sprite sheet, texture atlas."""

from __future__ import annotations

import json
from pathlib import Path

from pixelforge.animation.assembly import build_sprite_sheet, save_gif
from pixelforge.exporters.base import ExportAsset, Exporter, ExportOptions


class PngExporter(Exporter):
    format_id = "png"
    display_name = "PNG"

    def export(self, asset: ExportAsset, options: ExportOptions, dest: Path) -> list[Path]:
        frames = asset.scaled_frames(options.scale)
        paths = []
        for i, frame in enumerate(frames):
            suffix = f"_{i}" if len(frames) > 1 else ""
            path = dest / f"{options.base_name}{suffix}.png"
            frame.save(path)
            paths.append(path)
        return paths


class GifExporter(Exporter):
    format_id = "gif"
    display_name = "Animated GIF"

    def export(self, asset: ExportAsset, options: ExportOptions, dest: Path) -> list[Path]:
        path = dest / f"{options.base_name}.gif"
        save_gif(
            asset.scaled_frames(options.scale),
            str(path),
            frame_duration_ms=options.frame_duration_ms,
        )
        return [path]


class SpriteSheetExporter(Exporter):
    format_id = "sprite-sheet"
    display_name = "Sprite Sheet (PNG)"

    def export(self, asset: ExportAsset, options: ExportOptions, dest: Path) -> list[Path]:
        sheet = build_sprite_sheet(
            asset.scaled_frames(options.scale), columns=options.columns, padding=options.padding
        )
        path = dest / f"{options.base_name}_sheet.png"
        sheet.save(path)
        return [path]


class TextureAtlasExporter(Exporter):
    """Sprite sheet + JSON atlas metadata (generic hash format)."""

    format_id = "texture-atlas"
    display_name = "Texture Atlas (PNG + JSON)"

    def export(self, asset: ExportAsset, options: ExportOptions, dest: Path) -> list[Path]:
        frames = asset.scaled_frames(options.scale)
        cols = options.columns or len(frames)
        sheet = build_sprite_sheet(frames, columns=cols, padding=options.padding)
        sheet_path = dest / f"{options.base_name}_atlas.png"
        sheet.save(sheet_path)

        fw, fh = frames[0].size
        atlas = {
            "meta": {
                "image": sheet_path.name,
                "size": {"w": sheet.width, "h": sheet.height},
                "app": "PixelForge AI",
            },
            "frames": {
                f"{options.base_name}_{i}": {
                    "frame": {
                        "x": (i % cols) * (fw + options.padding),
                        "y": (i // cols) * (fh + options.padding),
                        "w": fw,
                        "h": fh,
                    },
                    "duration": options.frame_duration_ms,
                }
                for i in range(len(frames))
            },
        }
        json_path = dest / f"{options.base_name}_atlas.json"
        json_path.write_text(json.dumps(atlas, indent=2))
        return [sheet_path, json_path]
