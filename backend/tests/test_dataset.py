"""Dataset & LoRA-training toolkit tests (M4, D-001)."""

from __future__ import annotations

import base64
import io
import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from pixelforge.core.errors import BackendUnavailableError
from pixelforge.dataset.builder import LoadedImage, build_dataset, scan_directory
from pixelforge.dataset.caption import caption_image
from pixelforge.dataset.phash import cluster_duplicates, dhash, hamming_distance
from pixelforge.dataset.trainer import LoraTrainer


def _solid(color: tuple[int, int, int, int], size: int = 32) -> Image.Image:
    return Image.new("RGBA", (size, size), color)


def _noisy(seed: int, size: int = 32) -> Image.Image:
    rng = np.random.default_rng(seed)
    arr = rng.integers(0, 255, (size, size, 4), dtype=np.uint8)
    arr[..., 3] = 255
    return Image.fromarray(arr, "RGBA")


# --- perceptual hash -------------------------------------------------------


def test_dhash_is_deterministic_and_identical_for_same_image() -> None:
    image = _noisy(1)
    assert dhash(image) == dhash(image.copy())
    assert hamming_distance(dhash(image), dhash(image.copy())) == 0


def test_hamming_distance_of_distinct_images_is_large() -> None:
    a = dhash(_noisy(1))
    b = dhash(_noisy(999))
    assert hamming_distance(a, b) > 10


def test_cluster_duplicates_groups_near_duplicates() -> None:
    base = _solid((200, 30, 30, 255))
    near = base.copy()
    near.putpixel((0, 0), (198, 28, 32, 255))  # a tiny perturbation
    far = _noisy(7)
    hashes = [("a", dhash(base)), ("b", dhash(near)), ("c", dhash(far))]
    duplicate_of = cluster_duplicates(hashes)
    assert duplicate_of == {"b": "a"}  # b is a near-dup of a; c stands alone


# --- captioning ------------------------------------------------------------


def test_caption_is_deterministic() -> None:
    image = _noisy(3)
    assert caption_image(image) == caption_image(image.copy())


def test_caption_describes_size_and_hue() -> None:
    caption, tags = caption_image(_solid((30, 80, 200, 255)))
    assert "32x32" in caption
    assert "blue tones" in caption
    assert "pixel-art" in tags
    assert "32x32" in tags


def test_caption_handles_empty_sprite() -> None:
    caption, tags = caption_image(_solid((0, 0, 0, 0)))
    assert "empty" in caption
    assert "empty" in tags


# --- validation & build ----------------------------------------------------


def test_build_flags_corrupt_and_undersized() -> None:
    inputs = [
        LoadedImage(name="ok.png", image=_solid((10, 120, 200, 255))),
        LoadedImage(name="tiny.png", image=_solid((0, 0, 0, 255), size=4)),
        LoadedImage(name="corrupt.png", load_error="unreadable: bad header"),
    ]
    report = build_dataset(inputs)
    by_name = {i.name: i for i in report.items}
    assert by_name["ok.png"].valid
    assert not by_name["tiny.png"].valid
    assert "smaller than 8px" in by_name["tiny.png"].issues
    assert not by_name["corrupt.png"].valid
    assert report.valid_count == 1
    assert report.invalid_count == 2


def test_build_flags_oversize_but_keeps_valid() -> None:
    inputs = [LoadedImage(name="big.png", image=_solid((10, 20, 30, 255), size=1024))]
    report = build_dataset(inputs)
    item = report.items[0]
    assert item.valid  # oversize is a warning, not a rejection
    assert any("larger than training resolution" in issue for issue in item.issues)


def test_build_excludes_duplicates_from_manifest() -> None:
    inputs = [
        LoadedImage(name="a.png", image=_solid((200, 30, 30, 255))),
        LoadedImage(name="a_copy.png", image=_solid((200, 30, 30, 255))),
        LoadedImage(name="b.png", image=_noisy(11)),
    ]
    report = build_dataset(inputs)
    assert report.duplicate_count == 1
    assert len(report.clusters) == 1
    assert report.clusters[0].representative == "a.png"
    assert report.clusters[0].members == ["a_copy.png"]
    manifest_files = {r["file_name"] for r in report.manifest}
    assert manifest_files == {"a.png", "b.png"}  # the duplicate is left out
    assert report.lora_config.image_count == 2


def test_build_writes_manifest_and_config(tmp_path: Path) -> None:
    inputs = [LoadedImage(name="a.png", image=_solid((10, 120, 200, 255)))]
    report = build_dataset(inputs, out_dir=tmp_path)
    manifest_path = Path(report.manifest_path or "")
    config_path = Path(report.config_path or "")
    assert manifest_path.name == "manifest.jsonl"
    assert config_path.name == "lora_config.json"
    lines = manifest_path.read_text().strip().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["file_name"] == "a.png"
    assert record["width"] == 32
    config = json.loads(config_path.read_text())
    assert config["image_count"] == 1
    assert config["base_model"].startswith("black-forest-labs/FLUX")


def test_scan_directory_reads_images_and_flags_corrupt(tmp_path: Path) -> None:
    _solid((10, 120, 200, 255)).save(tmp_path / "good.png")
    (tmp_path / "broken.png").write_bytes(b"not a png")
    (tmp_path / "notes.txt").write_text("ignored")  # non-image, skipped
    loaded = scan_directory(tmp_path)
    names = {item.name for item in loaded}
    assert names == {"good.png", "broken.png"}
    by_name = {item.name: item for item in loaded}
    assert by_name["good.png"].image is not None
    assert by_name["broken.png"].image is None
    assert by_name["broken.png"].load_error is not None


# --- gated trainer ---------------------------------------------------------


def test_trainer_is_gated_off_without_ml_extras() -> None:
    trainer = LoraTrainer()
    # CI has neither torch nor peft; training must refuse rather than crash.
    assert trainer.is_available() is False
    with pytest.raises(BackendUnavailableError):
        trainer.train(Path("manifest.jsonl"), report_config(), Path("out"))


def test_trainer_plan_is_pure() -> None:
    plan = LoraTrainer().training_plan(Path("m.jsonl"), report_config(), Path("out"))
    assert plan[0] == "accelerate"
    assert any("--network_dim=16" in arg for arg in plan)


def report_config():
    return build_dataset([LoadedImage(name="a.png", image=_solid((1, 2, 3, 255)))]).lora_config


# --- API -------------------------------------------------------------------


def _b64(image: Image.Image) -> str:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()


def test_api_dataset_analyze(client) -> None:
    payload = {
        "images": [
            {"name": "a.png", "image_base64": _b64(_solid((200, 30, 30, 255)))},
            {"name": "a_copy.png", "image_base64": _b64(_solid((200, 30, 30, 255)))},
            {"name": "b.png", "image_base64": _b64(_noisy(5))},
            {"name": "bad.png", "image_base64": base64.b64encode(b"nope").decode()},
        ]
    }
    response = client.post("/api/dataset", json=payload)
    assert response.status_code == 200
    report = response.json()
    assert report["total"] == 4
    assert report["invalid_count"] == 1
    assert report["duplicate_count"] == 1
    assert report["lora_config"]["image_count"] == 2
    assert len(report["manifest"]) == 2


def test_api_dataset_rejects_empty(client) -> None:
    assert client.post("/api/dataset", json={"images": []}).status_code == 422
