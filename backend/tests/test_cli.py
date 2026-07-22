"""Tests for the headless CLI."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image

from pixelforge.cli import main


def test_generate_writes_pngs_and_prints_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(
        [
            "generate",
            "a knight",
            "--size",
            "16",
            "--seed",
            "42",
            "--batch",
            "2",
            "-o",
            str(tmp_path),
            "--quiet",
        ]
    )
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert len(payload["images"]) == 2
    for entry in payload["images"]:
        image = Image.open(entry["path"])
        assert image.size == (16, 16)
        assert entry["seed"] in (42, 43)


def test_generate_palette_lock(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = main(
        [
            "generate",
            "a slime",
            "--size",
            "16",
            "--seed",
            "1",
            "--palette",
            "monochrome-handheld",
            "-o",
            str(tmp_path),
            "--quiet",
        ]
    )
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert len(payload["images"][0]["palette_hex"]) <= 4


def test_generate_tileable(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    import numpy as np

    from pixelforge.generation.tileize import seam_score

    code = main(
        [
            "generate",
            "grass",
            "--size",
            "32",
            "--seed",
            "3",
            "--tileable",
            "-o",
            str(tmp_path),
            "--quiet",
        ]
    )
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    image = Image.open(payload["images"][0]["path"]).convert("RGBA")
    assert seam_score(np.asarray(image)) == 1.0


def test_tileset(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = main(
        [
            "tileset",
            "grass field",
            "--variants",
            "3",
            "--size",
            "32",
            "--seed",
            "5",
            "-o",
            str(tmp_path),
        ]
    )
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["variant_count"] == 3
    assert payload["coherent"] is True
    assert Path(payload["sheet_path"]).exists()
    assert all(Path(t["path"]).exists() for t in payload["tiles"])


def test_export_wang_blob(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    tile = tmp_path / "grass.png"
    Image.new("RGBA", (16, 16), (120, 180, 90, 255)).save(tile)
    code = main(["export", str(tile), "--format", "wang-blob", "-o", str(tmp_path / "out")])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert any(p.endswith("_blob.png") for p in payload["files"])
    assert any(p.endswith("_blob.json") for p in payload["files"])
    assert all(Path(p).exists() for p in payload["files"])


def test_export_spritesheet(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    frame = tmp_path / "frame.png"
    Image.new("RGBA", (16, 16), (255, 0, 0, 255)).save(frame)
    code = main(
        [
            "export",
            str(frame),
            str(frame),
            "--format",
            "sprite-sheet",
            "--scale",
            "2",
            "-o",
            str(tmp_path / "out"),
        ]
    )
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["files"]
    assert all(Path(p).exists() for p in payload["files"])


def test_unknown_palette_fails_cleanly(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["generate", "x", "--palette", "does-not-exist", "-o", str(tmp_path), "--quiet"])
    assert code == 2
    assert "unknown palette" in capsys.readouterr().err


def _patterned(seed: int, size: int = 32) -> Image.Image:
    """A sprite with internal structure — flat colors all collapse to the same perceptual hash."""
    import numpy as np

    rng = np.random.default_rng(seed)
    arr = rng.integers(0, 255, (size, size, 4), dtype=np.uint8)
    arr[..., 3] = 255
    return Image.fromarray(arr, "RGBA")


def test_dataset_build(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    sprites = tmp_path / "sprites"
    sprites.mkdir()
    _patterned(1).save(sprites / "a.png")
    _patterned(1).save(sprites / "a_copy.png")  # identical pixels → duplicate
    _patterned(99).save(sprites / "b.png")  # distinct
    (sprites / "broken.png").write_bytes(b"not a png")
    out = tmp_path / "out"
    code = main(["dataset", "build", str(sprites), "-o", str(out)])
    assert code == 0
    report = json.loads(capsys.readouterr().out)
    assert report["total"] == 4
    assert report["invalid_count"] == 1  # broken.png
    assert report["duplicate_count"] == 1  # a_copy.png
    assert report["lora_config"]["image_count"] == 2
    assert (out / "manifest.jsonl").exists()
    assert (out / "lora_config.json").exists()


def test_dataset_build_rejects_missing_dir(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["dataset", "build", str(tmp_path / "nope")]) == 2


def test_list_and_system(capsys: pytest.CaptureFixture[str]) -> None:
    for what in ("modes", "styles", "palettes", "export-formats", "backends"):
        assert main(["list", what]) == 0
        assert json.loads(capsys.readouterr().out)
    assert main(["system"]) == 0
    assert "device" in json.loads(capsys.readouterr().out)
