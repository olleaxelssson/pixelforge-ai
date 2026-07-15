import numpy as np
import pytest
from PIL import Image

from pixelforge.core.errors import InvalidPaletteError
from pixelforge.palettes.io import load_palette_file, save_palette_file
from pixelforge.palettes.model import Palette, hex_to_rgb, rgb_to_hex
from pixelforge.palettes.presets import BUILTIN_PALETTES
from pixelforge.palettes.quantize import apply_palette, extract_palette, swap_palette


def test_hex_roundtrip():
    assert hex_to_rgb("#ff8800") == (255, 136, 0)
    assert rgb_to_hex((255, 136, 0)) == "#ff8800"


def test_palette_rejects_bad_colors():
    with pytest.raises(ValueError):
        Palette(id="x", name="x", colors=["#zzz"])


def test_builtin_palettes_are_valid():
    assert len(BUILTIN_PALETTES) >= 6
    for palette in BUILTIN_PALETTES:
        assert palette.builtin
        assert len(palette.colors) >= 2


def test_apply_palette_maps_all_pixels():
    image = Image.new("RGBA", (8, 8), (200, 10, 10, 255))
    result = apply_palette(image, [(255, 0, 0), (0, 0, 255)])
    data = np.asarray(result)
    assert np.all(data[..., :3] == np.array([255, 0, 0]))
    assert np.all(data[..., 3] == 255)


def test_apply_palette_preserves_alpha():
    image = Image.new("RGBA", (4, 4), (0, 0, 0, 0))
    result = apply_palette(image, [(255, 255, 255)])
    assert np.all(np.asarray(result)[..., 3] == 0)


def test_extract_palette_limits_colors():
    rng = np.random.default_rng(1)
    noise = rng.integers(0, 255, (32, 32, 3), dtype=np.uint8)
    colors = extract_palette(Image.fromarray(noise, "RGB"), max_colors=8)
    assert 1 <= len(colors) <= 8


def test_ordered_dither_runs():
    image = Image.new("RGBA", (8, 8), (128, 128, 128, 255))
    result = apply_palette(image, [(0, 0, 0), (255, 255, 255)], ordered_dither=True)
    values = set(np.asarray(result)[..., 0].flatten().tolist())
    assert values <= {0, 255}


def test_swap_palette():
    source = Palette(id="s", name="s", colors=["#ff0000"])
    target = Palette(id="t", name="t", colors=["#00ff00"])
    image = Image.new("RGBA", (2, 2), (255, 0, 0, 255))
    swapped = swap_palette(image, source, target)
    assert np.all(np.asarray(swapped)[..., 1] == 255)


@pytest.mark.parametrize("suffix", [".json", ".pal", ".gpl"])
def test_palette_io_roundtrip(tmp_path, suffix):
    palette = Palette(id="test", name="Test", colors=["#112233", "#aabbcc"])
    path = tmp_path / f"test{suffix}"
    save_palette_file(palette, path)
    loaded = load_palette_file(path)
    assert loaded.colors == palette.colors


def test_palette_io_rejects_unknown_format(tmp_path):
    palette = Palette(id="test", name="Test", colors=["#112233"])
    with pytest.raises(InvalidPaletteError):
        save_palette_file(palette, tmp_path / "test.xyz")
