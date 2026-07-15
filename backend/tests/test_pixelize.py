import numpy as np
from PIL import Image

from pixelforge.pixelize import binarize_alpha, pixelize, remove_orphan_pixels


def test_pixelize_output_size():
    image = Image.new("RGBA", (256, 256), (100, 150, 200, 255))
    result = pixelize(image, 32, 32)
    assert result.size == (32, 32)


def test_pixelize_non_square():
    image = Image.new("RGBA", (256, 128), (10, 20, 30, 255))
    result = pixelize(image, 64, 16)
    assert result.size == (64, 16)


def test_pixelize_preserves_solid_color():
    image = Image.new("RGBA", (128, 128), (200, 50, 25, 255))
    result = pixelize(image, 16, 16)
    data = np.asarray(result)
    assert np.all(np.abs(data[..., :3].astype(int) - [200, 50, 25]) <= 1)


def test_pixelize_keeps_dominant_region_color():
    # Left half red, right half blue -> left cells red, right cells blue.
    array = np.zeros((128, 128, 4), dtype=np.uint8)
    array[:, :64] = [255, 0, 0, 255]
    array[:, 64:] = [0, 0, 255, 255]
    result = np.asarray(pixelize(Image.fromarray(array, "RGBA"), 8, 8))
    assert result[4, 1, 0] > 200 and result[4, 1, 2] < 50
    assert result[4, 6, 2] > 200 and result[4, 6, 0] < 50


def test_binarize_alpha():
    image = Image.new("RGBA", (2, 2), (255, 255, 255, 100))
    result = np.asarray(binarize_alpha(image))
    assert np.all(result[..., 3] == 0)
    image = Image.new("RGBA", (2, 2), (255, 255, 255, 200))
    result = np.asarray(binarize_alpha(image))
    assert np.all(result[..., 3] == 255)


def test_remove_orphan_pixels():
    array = np.zeros((5, 5, 4), dtype=np.uint8)
    array[2, 2] = [255, 0, 0, 255]  # isolated pixel
    array[0, 0] = [0, 255, 0, 255]
    array[0, 1] = [0, 255, 0, 255]  # connected pair survives
    result = np.asarray(remove_orphan_pixels(Image.fromarray(array, "RGBA")))
    assert result[2, 2, 3] == 0
    assert result[0, 0, 3] == 255 and result[0, 1, 3] == 255
