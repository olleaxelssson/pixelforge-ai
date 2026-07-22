"""Tileset generation tests (M23, D-001)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from pixelforge.generation.pipeline import GenerationPipeline
from pixelforge.generation.tileize import (
    cross_seam_metrics,
    edge_consistency,
    lock_edges_to,
    make_tileable,
)
from pixelforge.modes.registry import ModeRegistry
from pixelforge.palettes.service import PaletteService
from pixelforge.styles.registry import StyleRegistry
from pixelforge.tileset.service import TileSet, TileSetRequest


def _pipeline(tmp_path: Path) -> GenerationPipeline:
    return GenerationPipeline(
        backend_name="mock",
        outputs_dir=tmp_path,
        modes=ModeRegistry(),
        styles=StyleRegistry(),
        palettes=PaletteService(user_dir=tmp_path / "palettes"),
        diffusion_resolution=128,
    )


def _noisy(seed: int, size: int = 32) -> Image.Image:
    rng = np.random.default_rng(seed)
    arr = rng.integers(0, 255, (size, size, 4), dtype=np.uint8)
    arr[..., 3] = 255
    return Image.fromarray(arr, "RGBA")


# --- edge-lock helpers -----------------------------------------------------


def test_lock_edges_to_shares_reference_edges() -> None:
    reference = make_tileable(_noisy(1))  # self-tiling: left == right, top == bottom
    ref = np.asarray(reference)
    locked = np.asarray(lock_edges_to(_noisy(2), reference))
    # The locked tile inherits the reference's outer edges exactly...
    assert np.array_equal(locked[:, 0, :3], ref[:, 0, :3])
    assert np.array_equal(locked[:, -1, :3], ref[:, -1, :3])
    # ...so it abuts the reference cleanly and still self-tiles (ref left == ref right).
    assert np.array_equal(locked[:, 0, :3], locked[:, -1, :3])


def test_edge_consistency_perfect_for_shared_edges() -> None:
    reference = make_tileable(_noisy(3))
    locked = lock_edges_to(_noisy(4), reference)
    assert edge_consistency(np.asarray(reference), np.asarray(locked)) == 1.0


def test_cross_seam_metrics_flags_mismatch() -> None:
    a = np.zeros((8, 8, 4), np.uint8)
    a[..., 3] = 255
    b = np.full((8, 8, 4), 255, np.uint8)
    horizontal, vertical = cross_seam_metrics(a, b)  # black vs white → maximal mismatch
    assert horizontal == 1.0
    assert vertical == 1.0


# --- tileset service -------------------------------------------------------


def test_tileset_variants_abut_and_self_tile(tmp_path: Path) -> None:
    service = TileSet(_pipeline(tmp_path), tmp_path)
    request = TileSetRequest(prompt="grass field", variants=4, width=32, height=32, seed=5)
    report = service.generate("ts", request, lambda _s, _p: None)

    assert report.variant_count == 4
    assert report.coherent
    assert report.min_edge_consistency == 1.0

    images = [np.asarray(Image.open(tmp_path / t.filename).convert("RGBA")) for t in report.tiles]
    base = images[0]
    for variant in images[1:]:
        assert np.array_equal(base[:, -1, :3], variant[:, 0, :3])  # base right == variant left
        assert np.array_equal(base[-1, :, :3], variant[0, :, :3])  # base bottom == variant top
        assert np.array_equal(variant[:, 0, :3], variant[:, -1, :3])  # each still self-tiles


def test_tileset_locks_one_palette_across_variants(tmp_path: Path) -> None:
    service = TileSet(_pipeline(tmp_path), tmp_path)
    report = service.generate(
        "ts",
        TileSetRequest(prompt="stone", variants=3, width=32, height=32, seed=1),
        lambda *_: None,
    )
    palette = {tuple(int(v) for v in _hex(h)) for h in report.palette_hex}
    for tile in report.tiles:
        image = np.asarray(Image.open(tmp_path / tile.filename).convert("RGBA"))[..., :3]
        colors = {tuple(px) for px in image.reshape(-1, 3).tolist()}
        assert colors <= palette  # every variant stays on the one locked palette


def test_tileset_seed_anchored_deterministic(tmp_path: Path) -> None:
    request = TileSetRequest(prompt="dirt path", variants=3, width=32, height=32, seed=9)
    a = TileSet(_pipeline(tmp_path), tmp_path).generate("a", request, lambda *_: None)
    b = TileSet(_pipeline(tmp_path), tmp_path).generate("b", request, lambda *_: None)
    for ta, tb in zip(a.tiles, b.tiles, strict=True):
        assert ta.seed == tb.seed
        ia = np.asarray(Image.open(tmp_path / ta.filename))
        ib = np.asarray(Image.open(tmp_path / tb.filename))
        assert np.array_equal(ia, ib)
    # Variant seeds are the base seed plus the variant offset.
    assert [t.seed for t in a.tiles] == [9, 10, 11]


def test_tileset_assembles_blob_sheet(tmp_path: Path) -> None:
    service = TileSet(_pipeline(tmp_path), tmp_path)
    report = service.generate(
        "grass",
        TileSetRequest(prompt="grass", variants=4, width=32, height=32, seed=2),
        lambda *_: None,
    )
    sheet_path = tmp_path / report.sheet_filename
    assert sheet_path.exists()
    assert report.sheet_filename.endswith("_blob.png")
    sheet = Image.open(sheet_path)
    assert sheet.size == (8 * 32, 6 * 32)  # 47 tiles, 8-wide grid


def _hex(h: str):
    from pixelforge.palettes.model import hex_to_rgb

    return hex_to_rgb(h)


# --- wang-blob variant cycling ---------------------------------------------


def test_wang_blob_cycles_multiple_frames(tmp_path: Path) -> None:
    from pixelforge.exporters.base import ExportAsset, ExportOptions
    from pixelforge.exporters.wang_blob import WangBlobExporter

    red = Image.new("RGBA", (16, 16), (200, 40, 40, 255))
    blue = Image.new("RGBA", (16, 16), (40, 40, 200, 255))
    paths = WangBlobExporter().export(
        ExportAsset(frames=[red, blue]), ExportOptions(base_name="mix"), tmp_path
    )
    sheet = np.asarray(Image.open(paths[0]).convert("RGBA"))
    # Cell 0 (mask 0 = isolated) uses red; cell 1 uses blue — sample their centres.
    assert tuple(sheet[8, 8, :3]) == (200, 40, 40)
    assert tuple(sheet[8, 16 + 8, :3]) == (40, 40, 200)


# --- API -------------------------------------------------------------------


def test_api_tileset_generate(client) -> None:
    response = client.post(
        "/api/tileset/generate",
        json={"prompt": "grass", "variants": 3, "width": 32, "height": 32, "seed": 4},
    )
    assert response.status_code == 200
    report = response.json()
    assert report["variant_count"] == 3
    assert report["coherent"] is True
    assert client.get(f"/api/images/{report['sheet_filename']}").status_code == 200
    assert client.get(f"/api/images/{report['tiles'][0]['filename']}").status_code == 200


def test_api_tileset_rejects_unknown_style(client) -> None:
    response = client.post("/api/tileset/generate", json={"prompt": "x", "style": "nope"})
    assert response.status_code == 422
