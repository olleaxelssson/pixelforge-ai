"""Content hashing + perceptual hashing for deduplication and similarity warnings.

- ``sha256_bytes`` is the exact-duplicate key (same file bytes → same asset).
- ``dhash`` is a perceptual difference-hash for near-duplicate detection: it survives re-encoding,
  small palette shifts, and format changes. NEAREST downscaling keeps it stable across machines.
"""

from __future__ import annotations

import hashlib

import numpy as np
from PIL import Image

_HASH_SIZE = 8


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def dhash(image: Image.Image, size: int = _HASH_SIZE) -> str:
    """64-bit difference hash as 16 hex chars. Compares horizontally adjacent pixels."""
    small = image.convert("L").resize((size + 1, size), Image.Resampling.NEAREST)
    pixels = np.asarray(small, dtype=np.int16)
    bits = pixels[:, 1:] > pixels[:, :-1]
    value = 0
    for bit in bits.flatten():
        value = (value << 1) | int(bit)
    return f"{value:016x}"


def hamming(a: str, b: str) -> int:
    """Bit distance between two hex dHashes (0 = identical, 64 = maximally different)."""
    if not a or not b:
        return 64
    return bin(int(a, 16) ^ int(b, 16)).count("1")
