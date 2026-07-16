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


def test_list_and_system(capsys: pytest.CaptureFixture[str]) -> None:
    for what in ("modes", "styles", "palettes", "export-formats", "backends"):
        assert main(["list", what]) == 0
        assert json.loads(capsys.readouterr().out)
    assert main(["system"]) == 0
    assert "device" in json.loads(capsys.readouterr().out)
