"""Aseprite exporter tests (M5/M20): round-trip, byte-exact golden, determinism, registry, CLI."""

from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
from PIL import Image

from pixelforge.cli import main
from pixelforge.exporters.aseprite import (
    AsepriteExporter,
    build_aseprite,
    parse_aseprite,
)
from pixelforge.exporters.base import ExportAsset, ExportOptions
from pixelforge.exporters.registry import get_exporter, list_exporters

_GOLDEN = Path(__file__).parent / "golden" / "walk.aseprite"


def _frame(base: tuple[int, int, int], top: tuple[int, int, int]) -> Image.Image:
    arr = np.zeros((8, 8, 4), np.uint8)
    arr[2:6, 2:6] = [*base, 255]
    arr[2:4, 2:6] = [*top, 255]  # a lighter band → a second color
    return Image.fromarray(arr, "RGBA")


def _frames() -> list[Image.Image]:
    return [_frame((70, 110, 180), (120, 150, 220)), _frame((70, 110, 180), (40, 70, 130))]


def test_roundtrips_frames_palette_and_pixels() -> None:
    frames = _frames()
    parsed = parse_aseprite(build_aseprite(frames, frame_duration_ms=100))

    assert parsed.frames == 2
    assert (parsed.width, parsed.height) == (8, 8)
    assert parsed.color_depth == 8  # indexed
    assert parsed.palette[0] == (0, 0, 0, 0)  # index 0 is transparent
    # Parsing the indexed cels back reconstructs every original frame exactly.
    for i, frame in enumerate(frames):
        assert np.array_equal(parsed.frame_rgba(i), np.asarray(frame.convert("RGBA")))


def test_is_deterministic() -> None:
    assert build_aseprite(_frames(), 100) == build_aseprite(_frames(), 100)


def test_matches_golden() -> None:
    """Uncompressed cels → byte-stable across machines, so an exact golden works in CI."""
    data = build_aseprite(_frames(), frame_duration_ms=100)
    if os.environ.get("PIXELFORGE_UPDATE_GOLDEN") == "1":
        _GOLDEN.parent.mkdir(exist_ok=True)
        _GOLDEN.write_bytes(data)
        return
    assert _GOLDEN.exists(), "missing golden; run with PIXELFORGE_UPDATE_GOLDEN=1"
    assert data == _GOLDEN.read_bytes()


def test_over_255_colors_falls_back_to_nearest() -> None:
    # A 16x16 sprite with 256 distinct opaque colors → capped to 255 opaque + transparent.
    arr = np.zeros((16, 16, 4), np.uint8)
    for i in range(256):
        arr[i // 16, i % 16] = [i, (i * 5) % 256, (i * 11) % 256, 255]
    parsed = parse_aseprite(build_aseprite([Image.fromarray(arr, "RGBA")]))
    assert len(parsed.palette) == 256  # 255 opaque + transparent, never exceeds 256
    assert max(parsed.frame_indices[0]) <= 255


def test_registered_in_exporter_registry() -> None:
    assert get_exporter("aseprite").display_name == "Aseprite (.aseprite)"
    assert any(e["format_id"] == "aseprite" for e in list_exporters())


def test_exporter_writes_file(tmp_path) -> None:
    paths = AsepriteExporter().export(
        ExportAsset(frames=_frames()), ExportOptions(base_name="walk"), tmp_path
    )
    assert paths == [tmp_path / "walk.aseprite"]
    assert parse_aseprite(paths[0].read_bytes()).frames == 2


def test_cli_export_aseprite(tmp_path, capsys) -> None:
    src = tmp_path / "sprite.png"
    _frames()[0].save(src)
    out = tmp_path / "out"
    assert main(["export", str(src), "--format", "aseprite", "-o", str(out)]) == 0
    files = json.loads(capsys.readouterr().out)["files"]
    assert files[0].endswith(".aseprite")
    assert parse_aseprite(Path(files[0]).read_bytes()).width == 8
