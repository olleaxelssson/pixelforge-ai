"""Aseprite (.aseprite/.ase) writer (M5, D-001) — round-trip into the most-used pixel editor.

Writes the documented Aseprite binary format (aseprite/aseprite `docs/ase-file-specs.md`, MIT): an
**indexed** (8bpp) sprite with one layer, the frames as cels, and the palette built from the frames'
own colors. Cels are written **uncompressed** (cel type 0), so the output is byte-deterministic
across machines (no zlib version dependency) — which lets a byte-exact golden test run in CI.
Aseprite reads uncompressed cels fine.

The format is a header + one block per frame; each frame is a small header followed by typed chunks.
``build_aseprite`` is a pure ``list[Image] -> bytes`` serializer; ``parse_aseprite`` reads enough of
it back (header, palette, per-frame indices) to verify structure in tests.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image

from pixelforge.exporters.base import ExportAsset, Exporter, ExportOptions

_HEADER_MAGIC = 0xA5E0
_FRAME_MAGIC = 0xF1FA
_ALPHA_CUTOFF = 128  # pixels below this alpha are the transparent index (0)
_MAX_COLORS = 256

# Chunk types
_CHUNK_OLD_PALETTE = 0x0004
_CHUNK_LAYER = 0x2004
_CHUNK_CEL = 0x2005
_CHUNK_PALETTE = 0x2019

RGBA = tuple[int, int, int, int]


def _string(text: str) -> bytes:
    data = text.encode("utf-8")
    return struct.pack("<H", len(data)) + data


def _chunk(chunk_type: int, body: bytes) -> bytes:
    return struct.pack("<IH", 6 + len(body), chunk_type) + body


def _build_palette(frames: list[Image.Image]) -> tuple[list[RGBA], dict[RGBA, int]]:
    """Index 0 is transparent; opaque colors follow in a deterministic (sorted) order."""
    colors: set[tuple[int, int, int]] = set()
    for frame in frames:
        rgba = np.asarray(frame.convert("RGBA"), dtype=np.uint8)
        opaque = rgba[rgba[..., 3] >= _ALPHA_CUTOFF][:, :3]
        for r, g, b in np.unique(opaque, axis=0):
            colors.add((int(r), int(g), int(b)))

    ordered = sorted(colors)[: _MAX_COLORS - 1]  # reserve slot 0 for transparency
    palette: list[RGBA] = [(0, 0, 0, 0)]
    index: dict[RGBA, int] = {}
    for i, (r, g, b) in enumerate(ordered, start=1):
        palette.append((r, g, b, 255))
        index[(r, g, b, 255)] = i
    return palette, index


def _nearest_index(rgb: tuple[int, int, int], palette: list[RGBA]) -> int:
    """Nearest opaque palette color (used only when a sprite exceeds 255 colors)."""
    best_i, best_d = 1, 1 << 30
    for i in range(1, len(palette)):
        pr, pg, pb, _ = palette[i]
        d = (pr - rgb[0]) ** 2 + (pg - rgb[1]) ** 2 + (pb - rgb[2]) ** 2
        if d < best_d:
            best_i, best_d = i, d
    return best_i


def _indices(frame: Image.Image, palette: list[RGBA], index: dict[RGBA, int]) -> bytes:
    rgba = np.asarray(frame.convert("RGBA"), dtype=np.uint8)
    height, width = rgba.shape[:2]
    out = bytearray(width * height)
    for y in range(height):
        for x in range(width):
            r, g, b, a = (int(v) for v in rgba[y, x])
            if a < _ALPHA_CUTOFF:
                continue  # transparent -> index 0 (already zero)
            out[y * width + x] = index.get((r, g, b, 255)) or _nearest_index((r, g, b), palette)
    return bytes(out)


def _layer_chunk(name: str = "Layer 1") -> bytes:
    body = struct.pack(
        "<HHHHHHB",
        3,  # flags: visible | editable
        0,  # layer kind: normal image layer
        0,  # child level
        0,  # default width (ignored)
        0,  # default height (ignored)
        0,  # blend mode: normal
        255,  # opacity
    )
    body += b"\x00\x00\x00" + _string(name)
    return _chunk(_CHUNK_LAYER, body)


def _new_palette_chunk(palette: list[RGBA]) -> bytes:
    body = struct.pack("<III", len(palette), 0, len(palette) - 1) + b"\x00" * 8
    for r, g, b, a in palette:
        body += struct.pack("<HBBBB", 0, r, g, b, a)  # flags=0 (no name)
    return _chunk(_CHUNK_PALETTE, body)


def _old_palette_chunk(palette: list[RGBA]) -> bytes:
    count = 0 if len(palette) == 256 else len(palette)
    body = struct.pack("<HBB", 1, 0, count)  # 1 packet, skip 0, count (0 == 256)
    for r, g, b, _ in palette:
        body += struct.pack("<BBB", r, g, b)
    return _chunk(_CHUNK_OLD_PALETTE, body)


def _cel_chunk(width: int, height: int, indices: bytes) -> bytes:
    body = struct.pack("<HhhBH", 0, 0, 0, 255, 0)  # layer 0, x, y, opacity, cel type 0 (raw)
    body += b"\x00" * 7  # z-index (SHORT) + 5 reserved — zero for all format versions
    body += struct.pack("<HH", width, height) + indices
    return _chunk(_CHUNK_CEL, body)


def build_aseprite(
    frames: list[Image.Image], frame_duration_ms: int = 100, grid: int = 16
) -> bytes:
    """Serialize frames (same size) into an indexed ``.aseprite`` file. Pure and deterministic."""
    if not frames:
        raise ValueError("no frames to export")
    width, height = frames[0].size
    if any(f.size != (width, height) for f in frames):
        raise ValueError("all frames must share the same size")

    palette, index = _build_palette(frames)

    blocks: list[bytes] = []
    for i, frame in enumerate(frames):
        chunks = b""
        chunk_count = 1  # cel
        if i == 0:
            chunks += _layer_chunk() + _old_palette_chunk(palette) + _new_palette_chunk(palette)
            chunk_count += 3
        chunks += _cel_chunk(width, height, _indices(frame, palette, index))
        frame_header = struct.pack(
            "<IHHH2xI",
            16 + len(chunks),  # bytes in this frame
            _FRAME_MAGIC,
            min(chunk_count, 0xFFFF),  # old chunk count (WORD)
            frame_duration_ms,
            chunk_count,  # new chunk count (DWORD)
        )
        blocks.append(frame_header + chunks)

    body = b"".join(blocks)
    header = struct.pack(
        "<IHHHHHIH2IB3xHBB2h2H",
        128 + len(body),  # file size
        _HEADER_MAGIC,
        len(frames),
        width,
        height,
        8,  # color depth: indexed
        1,  # flags: layer opacity is valid
        0,  # speed (deprecated)
        0,
        0,
        0,  # transparent palette index
        len(palette),  # number of colors
        1,  # pixel width
        1,  # pixel height
        0,  # grid x
        0,  # grid y
        grid,  # grid width
        grid,  # grid height
    )
    header += b"\x00" * 84  # reserved
    return header + body


# --- minimal reader (for tests / verification) ------------------------------


@dataclass
class ParsedAseprite:
    width: int
    height: int
    frames: int
    color_depth: int
    palette: list[RGBA] = field(default_factory=list)
    frame_indices: list[bytes] = field(default_factory=list)  # per-frame width*height indices

    def frame_rgba(self, i: int) -> np.ndarray:
        indices = np.frombuffer(self.frame_indices[i], dtype=np.uint8)
        lut = np.array(self.palette, dtype=np.uint8)
        return lut[indices].reshape(self.height, self.width, 4)


def parse_aseprite(data: bytes) -> ParsedAseprite:
    (_size, magic, frames, width, height, depth) = struct.unpack_from("<IHHHHH", data, 0)
    if magic != _HEADER_MAGIC:
        raise ValueError("not an aseprite file")
    parsed = ParsedAseprite(width=width, height=height, frames=frames, color_depth=depth)

    offset = 128
    for _ in range(frames):
        (frame_bytes, fmagic, _old, _dur) = struct.unpack_from("<IHHH", data, offset)
        if fmagic != _FRAME_MAGIC:
            raise ValueError("bad frame magic")
        chunk_count = struct.unpack_from("<I", data, offset + 12)[0]
        pos = offset + 16
        for _ in range(chunk_count):
            chunk_size, chunk_type = struct.unpack_from("<IH", data, pos)
            cbody = pos + 6
            if chunk_type == _CHUNK_PALETTE:
                size = struct.unpack_from("<I", data, cbody)[0]
                entry = cbody + 20
                palette: list[RGBA] = []
                for _c in range(size):
                    _flags, r, g, b, a = struct.unpack_from("<HBBBB", data, entry)
                    palette.append((r, g, b, a))
                    entry += 6
                parsed.palette = palette
            elif chunk_type == _CHUNK_CEL:
                cel_type = struct.unpack_from("<H", data, cbody + 7)[0]
                if cel_type != 0:
                    raise ValueError("expected an uncompressed cel")
                w, h = struct.unpack_from("<HH", data, cbody + 16)
                pixels = data[cbody + 20 : cbody + 20 + w * h]
                parsed.frame_indices.append(pixels)
            pos += chunk_size
        offset += frame_bytes
    return parsed


class AsepriteExporter(Exporter):
    format_id = "aseprite"
    display_name = "Aseprite (.aseprite)"

    def export(self, asset: ExportAsset, options: ExportOptions, dest: Path) -> list[Path]:
        data = build_aseprite(
            asset.scaled_frames(options.scale), frame_duration_ms=options.frame_duration_ms
        )
        path = dest / f"{options.base_name}.aseprite"
        path.write_bytes(data)
        return [path]
