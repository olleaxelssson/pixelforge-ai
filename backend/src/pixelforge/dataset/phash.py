"""Perceptual hashing + near-duplicate clustering (M4, D-001).

A difference hash (dHash): downscale to 9x8 grayscale, then compare horizontally adjacent pixels →
64 bits. The resize uses NEAREST so the hash is **bit-for-bit deterministic across machines** (no
interpolation), which keeps the dedup tests stable everywhere. Identical images hash identically;
near-duplicates land within a small Hamming distance.
"""

from __future__ import annotations

import numpy as np
from PIL import Image

_HASH_SIZE = 8
DEFAULT_DUP_DISTANCE = 6  # <= this many differing bits (of 64) counts as a near-duplicate


def dhash(image: Image.Image) -> str:
    """Return a 16-hex-char (64-bit) difference hash."""
    small = image.convert("L").resize((_HASH_SIZE + 1, _HASH_SIZE), Image.Resampling.NEAREST)
    pixels = np.asarray(small, dtype=np.int16)
    bits = pixels[:, 1:] > pixels[:, :-1]  # 8x8 comparisons
    value = 0
    for bit in bits.flatten():
        value = (value << 1) | int(bit)
    return f"{value:016x}"


def hamming_distance(a: str, b: str) -> int:
    if not a or not b:
        return 64
    return bin(int(a, 16) ^ int(b, 16)).count("1")


def cluster_duplicates(
    hashes: list[tuple[str, str]], max_distance: int = DEFAULT_DUP_DISTANCE
) -> dict[str, str]:
    """Greedy single-link clustering by Hamming distance.

    ``hashes`` is a list of ``(name, phash)`` in a stable order; the first member of each cluster
    is its representative. Returns a map ``member_name -> representative_name`` for near-duplicates
    only (representatives are not in the map).
    """
    representatives: list[tuple[str, str]] = []  # (name, phash)
    duplicate_of: dict[str, str] = {}
    for name, phash in hashes:
        if not phash:
            continue
        match = next(
            (
                rep
                for rep, rhash in representatives
                if hamming_distance(phash, rhash) <= max_distance
            ),
            None,
        )
        if match is None:
            representatives.append((name, phash))
        else:
            duplicate_of[name] = match
    return duplicate_of
