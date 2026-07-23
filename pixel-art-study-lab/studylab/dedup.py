"""Duplicate and near-duplicate detection.

Three layers, cheapest first:
1. **exact** — identical file bytes (SHA-256), caught before import.
2. **perceptual** — small Hamming distance between dHashes (re-encodes, palette tweaks).
3. **semantic** — high cosine similarity between local embeddings (same subject/style).

Surfaced as warnings so the user never *accidentally* re-collects or reproduces a specific work.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from studylab.db import Database
from studylab.hashing import hamming

PHASH_THRESHOLD = 6  # bits (of 64)
COSINE_THRESHOLD = 0.93


@dataclass
class DuplicateWarning:
    asset_id: int
    kind: str  # 'perceptual' | 'semantic'
    score: float  # hamming distance (perceptual) or cosine similarity (semantic)


def near_duplicates(
    db: Database,
    *,
    phash: str,
    embedding: np.ndarray | None,
    phash_threshold: int = PHASH_THRESHOLD,
    cosine_threshold: float = COSINE_THRESHOLD,
    exclude_id: int | None = None,
) -> list[DuplicateWarning]:
    warnings: dict[int, DuplicateWarning] = {}

    for asset_id, other in db.all_phashes():
        if asset_id == exclude_id:
            continue
        dist = hamming(phash, other)
        if dist <= phash_threshold:
            warnings[asset_id] = DuplicateWarning(asset_id, "perceptual", float(dist))

    if embedding is not None:
        for asset_id, blob, dim in db.all_embeddings():
            if asset_id == exclude_id or dim != embedding.shape[0]:
                continue
            other = np.frombuffer(blob, dtype=np.float32)
            sim = float(np.dot(embedding, other))
            if sim >= cosine_threshold and asset_id not in warnings:
                warnings[asset_id] = DuplicateWarning(asset_id, "semantic", round(sim, 3))

    return sorted(warnings.values(), key=lambda w: w.asset_id)
