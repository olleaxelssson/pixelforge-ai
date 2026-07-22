"""Seamless tiling & auto-tile export tests (M22, D-001)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from pixelforge.exporters.base import ExportAsset, ExportOptions
from pixelforge.exporters.registry import get_exporter, list_exporters
from pixelforge.exporters.wang_blob import NE, WangBlobExporter, blob_masks
from pixelforge.generation.tileize import make_tileable, seam_metrics, seam_score
from pixelforge.qa.models import DetectorContext
from pixelforge.qa.registry import DetectorRegistry


def _noisy(seed: int, size: int = 32) -> Image.Image:
    rng = np.random.default_rng(seed)
    arr = rng.integers(0, 255, (size, size, 4), dtype=np.uint8)
    arr[..., 3] = 255
    return Image.fromarray(arr, "RGBA")


# --- seam-blend -----------------------------------------------------------


def test_make_tileable_matches_opposite_edges() -> None:
    tiled = np.asarray(make_tileable(_noisy(1)))
    assert np.array_equal(tiled[:, 0, :3], tiled[:, -1, :3])  # left == right
    assert np.array_equal(tiled[0, :, :3], tiled[-1, :, :3])  # top == bottom


def test_make_tileable_raises_seam_score() -> None:
    image = _noisy(2)
    before = seam_score(np.asarray(image))
    after = seam_score(np.asarray(make_tileable(image)))
    assert before < 0.9
    assert after == pytest.approx(1.0)


def test_make_tileable_leaves_interior_untouched() -> None:
    image = _noisy(3, size=32)
    original = np.asarray(image)
    tiled = np.asarray(make_tileable(image, blend_fraction=0.25))
    # A 25% band on each side is blended; the central column/row is untouched.
    assert np.array_equal(tiled[16, 16], original[16, 16])


def test_seam_metrics_zero_for_flat_image() -> None:
    flat = Image.new("RGBA", (16, 16), (80, 120, 160, 255))
    horizontal, vertical = seam_metrics(np.asarray(flat))
    assert horizontal == 0.0
    assert vertical == 0.0


# --- seam detector --------------------------------------------------------


def _seam_findings(rgba: np.ndarray, *, tileable: bool):
    registry = DetectorRegistry()
    return [
        f
        for d in registry.list()
        if d.name == "seam-discontinuity"
        for f in d.detect(rgba, DetectorContext(tileable=tileable))
    ]


def test_seam_detector_only_fires_when_tileable() -> None:
    seamed = np.asarray(_noisy(4))  # random image → strong seam
    assert _seam_findings(seamed, tileable=False) == []
    assert len(_seam_findings(seamed, tileable=True)) >= 1


def test_seam_detector_silent_on_seamless_sprite() -> None:
    tiled = np.asarray(make_tileable(_noisy(5)))
    assert _seam_findings(tiled, tileable=True) == []


# --- wang/blob exporter ---------------------------------------------------


def test_blob_masks_are_47() -> None:
    masks = blob_masks()
    assert len(masks) == 47
    assert len(set(masks)) == 47
    # No canonical mask has a corner bit without both its adjacent edges.
    for mask in masks:
        if mask & NE:
            assert mask & 1 and mask & 2  # N and E


def test_wang_blob_exporter_writes_sheet_and_mapping(tmp_path: Path) -> None:
    base = Image.new("RGBA", (16, 16), (120, 180, 90, 255))
    paths = WangBlobExporter().export(
        ExportAsset(frames=[base]), ExportOptions(base_name="grass"), tmp_path
    )
    sheet_path, json_path = paths
    assert sheet_path.name == "grass_blob.png"
    sheet = Image.open(sheet_path)
    assert sheet.size == (8 * 16, 6 * 16)  # 47 tiles in an 8-wide grid → 6 rows
    meta = json.loads(json_path.read_text())
    assert meta["meta"]["tiles"] == 47
    assert len(meta["tiles"]) == 47
    # The fully-surrounded tile (all 8 neighbours) is left completely filled.
    full = next(t for t in meta["tiles"] if t["mask"] == 255)
    tile = sheet.crop((full["x"], full["y"], full["x"] + 16, full["y"] + 16))
    assert np.asarray(tile)[..., 3].min() == 255  # no carving → fully opaque


def test_wang_blob_carves_isolated_tile(tmp_path: Path) -> None:
    base = Image.new("RGBA", (16, 16), (120, 180, 90, 255))
    _, json_path = WangBlobExporter().export(
        ExportAsset(frames=[base]), ExportOptions(base_name="t"), tmp_path
    )
    meta = json.loads(json_path.read_text())
    sheet = Image.open(tmp_path / "t_blob.png")
    isolated = next(t for t in meta["tiles"] if t["mask"] == 0)  # no neighbours
    tile = np.asarray(
        sheet.crop((isolated["x"], isolated["y"], isolated["x"] + 16, isolated["y"] + 16))
    )
    # All four edge bands carved away → transparent border, opaque centre.
    assert tile[0, 0, 3] == 0
    assert tile[8, 8, 3] == 255


def test_wang_blob_registered() -> None:
    assert get_exporter("wang-blob").format_id == "wang-blob"
    assert any(e["format_id"] == "wang-blob" for e in list_exporters())


# --- API ------------------------------------------------------------------


def _wait(client, job_id, timeout=30.0):
    import time

    deadline = time.time() + timeout
    while time.time() < deadline:
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] in ("completed", "failed", "cancelled"):
            return job
        time.sleep(0.05)
    raise TimeoutError(job_id)


def test_api_generate_tileable(client) -> None:
    response = client.post(
        "/api/generate",
        json={
            "prompt": "grass",
            "mode": "tileset",
            "width": 32,
            "height": 32,
            "seed": 3,
            "tileable": True,
        },
    )
    assert response.status_code == 202
    job = _wait(client, response.json()["id"])
    assert job["status"] == "completed"
    rgba = np.asarray(
        Image.open(_image_bytes(client, job["result"]["images"][0]["filename"])).convert("RGBA")
    )
    assert np.array_equal(rgba[:, 0, :3], rgba[:, -1, :3])


def _image_bytes(client, filename):
    import io

    return io.BytesIO(client.get(f"/api/images/{filename}").content)


def test_api_qa_seam_check(client) -> None:
    import base64
    import io

    seamed = _noisy(9)
    buffer = io.BytesIO()
    seamed.save(buffer, format="PNG")
    data = base64.b64encode(buffer.getvalue()).decode()
    report = client.post("/api/qa", json={"image_base64": data, "tileable": True}).json()["report"]
    assert any(f["detector"] == "seam-discontinuity" for f in report["findings"])
    # Without the flag, no seam finding.
    plain = client.post("/api/qa", json={"image_base64": data}).json()["report"]
    assert not any(f["detector"] == "seam-discontinuity" for f in plain["findings"])
