"""Assemble frames into sprite sheets and animated GIF previews."""

from __future__ import annotations

from PIL import Image


def build_sprite_sheet(
    frames: list[Image.Image], columns: int | None = None, padding: int = 0
) -> Image.Image:
    if not frames:
        raise ValueError("no frames to assemble")
    cols = columns or len(frames)
    rows = (len(frames) + cols - 1) // cols
    fw, fh = frames[0].size
    sheet = Image.new(
        "RGBA", (cols * fw + (cols - 1) * padding, rows * fh + (rows - 1) * padding), (0, 0, 0, 0)
    )
    for i, frame in enumerate(frames):
        col, row = i % cols, i // cols
        sheet.paste(frame, (col * (fw + padding), row * (fh + padding)))
    return sheet


def save_gif(
    frames: list[Image.Image], path: str, frame_duration_ms: int = 120, loop: bool = True
) -> None:
    if not frames:
        raise ValueError("no frames to save")
    converted = [f.convert("RGBA") for f in frames]
    converted[0].save(
        path,
        save_all=True,
        append_images=converted[1:],
        duration=frame_duration_ms,
        loop=0 if loop else 1,
        disposal=2,
        transparency=0,
    )
