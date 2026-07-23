"""A small, honest local tagger — a k-nearest-neighbours classifier over the local embeddings.

This is **not** a foundation model and makes no such claim. It learns nothing beyond "images that
embed near each other tend to share tags": it stores the embeddings of already-tagged assets together
with their human/VLM tags, and to tag a new image it looks at the *k* nearest examples and proposes
the tags they agree on, weighted by similarity.

It is trained **only on assets you already hold with an allowed license and human-supplied tags** —
never on scraped-but-unlicensed data, and never on the model's own auto-tags (those are excluded so
the classifier can't reinforce its own guesses). The trained index is a plain ``.npz`` you can
inspect, copy, or delete.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from studylab.config import ALLOWED_LICENSES
from studylab.db import Database

# Tags produced by the automatic describer; excluded from training so the tagger
# never learns from its own output.
_EXCLUDED_ORIGINS = frozenset({"auto"})


@dataclass
class TagSuggestion:
    tag: str
    score: float  # 0..1 confidence (sum of neighbour similarities, normalised)


class TagModel:
    """kNN tag classifier. Fit from the DB's labelled+licensed subset; serialise to ``.npz``."""

    def __init__(self, embeddings: np.ndarray, tag_sets: list[list[str]], dim: int) -> None:
        self.embeddings = embeddings  # (N, dim) float32, L2-normalised
        self.tag_sets = tag_sets  # parallel list of tag lists
        self.dim = dim

    @property
    def size(self) -> int:
        return len(self.tag_sets)

    @classmethod
    def fit(cls, db: Database, *, min_examples: int = 1) -> TagModel:
        """Build from every asset that has an allowed license and at least one non-auto tag."""
        vectors: list[np.ndarray] = []
        tag_sets: list[list[str]] = []
        dim = 0
        for asset_id, blob, d in db.all_embeddings():
            asset = db.get_asset(asset_id)
            if not asset or asset.get("license") not in ALLOWED_LICENSES:
                continue
            tags = [
                t["tag"]
                for t in db.get_tags(asset_id)
                if t["origin"] not in _EXCLUDED_ORIGINS
            ]
            if not tags:
                continue
            vectors.append(np.frombuffer(blob, dtype=np.float32))
            tag_sets.append(sorted(set(tags)))
            dim = d
        if len(vectors) < min_examples:
            return cls(np.zeros((0, dim or 1), dtype=np.float32), [], dim or 1)
        return cls(np.vstack(vectors).astype(np.float32), tag_sets, dim)

    def suggest(
        self, embedding: np.ndarray, *, k: int = 5, threshold: float = 0.35, max_tags: int = 6
    ) -> list[TagSuggestion]:
        """Suggest tags for a query embedding from its ``k`` nearest labelled neighbours."""
        if self.size == 0 or embedding.shape[0] != self.dim:
            return []
        sims = self.embeddings @ embedding.astype(np.float32)
        order = np.argsort(sims)[::-1][:k]
        weights: dict[str, float] = {}
        total = 0.0
        for idx in order:
            sim = float(sims[idx])
            if sim <= 0:
                continue
            total += sim
            for tag in self.tag_sets[idx]:
                weights[tag] = weights.get(tag, 0.0) + sim
        if total <= 0:
            return []
        scored = [
            TagSuggestion(tag, round(w / total, 3))
            for tag, w in weights.items()
            if w / total >= threshold
        ]
        scored.sort(key=lambda s: s.score, reverse=True)
        return scored[:max_tags]

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            path,
            embeddings=self.embeddings,
            tag_sets=np.array(json.dumps(self.tag_sets)),
            dim=np.array(self.dim),
        )

    @classmethod
    def load(cls, path: Path) -> TagModel:
        data = np.load(path, allow_pickle=False)
        tag_sets = json.loads(str(data["tag_sets"]))
        return cls(data["embeddings"].astype(np.float32), tag_sets, int(data["dim"]))
