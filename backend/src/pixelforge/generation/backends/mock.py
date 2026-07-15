"""Deterministic procedural backend for tests, CI, and UI development.

Produces seeded, prompt-influenced abstract sprites so the full pipeline
(pixelize → palette → cleanup → export) can be exercised without model weights.
"""

from __future__ import annotations

import hashlib

import numpy as np
from PIL import Image

from pixelforge.generation.backends.base import DiffusionSpec, GenerationBackend, ProgressFn


class MockBackend(GenerationBackend):
    name = "mock"

    def is_available(self) -> bool:
        return True

    def generate(self, spec: DiffusionSpec, on_progress: ProgressFn) -> list[Image.Image]:
        images = []
        for index in range(spec.batch_size):
            images.append(self._render(spec, index))
            on_progress((index + 1) / spec.batch_size)
        return images

    def _render(self, spec: DiffusionSpec, index: int) -> Image.Image:
        digest = hashlib.sha256(f"{spec.prompt}|{spec.seed}|{index}".encode()).digest()
        rng = np.random.default_rng(int.from_bytes(digest[:8], "little"))
        size = spec.resolution

        # Layered value-noise blobs mirrored horizontally -> sprite-like shapes.
        yy, xx = np.mgrid[0:size, 0:size].astype(np.float32) / size
        canvas: np.ndarray = np.zeros((size, size), dtype=np.float32)
        for _ in range(6):
            cx, cy = rng.uniform(0.2, 0.8), rng.uniform(0.2, 0.8)
            radius = rng.uniform(0.08, 0.3)
            blob = np.exp(-(((xx - cx) ** 2 + (yy - cy) ** 2) / (2 * radius**2)))
            canvas += blob * rng.uniform(0.5, 1.0)
        canvas = np.maximum(canvas, canvas[:, ::-1]).astype(np.float32)  # horizontal symmetry
        mask = canvas > np.percentile(canvas, 55)

        base = rng.uniform(0, 1, 3)
        shade = (canvas / canvas.max())[..., None]
        rgb = (base[None, None, :] * (0.4 + 0.6 * shade) * 255).astype(np.uint8)
        alpha = (mask * 255).astype(np.uint8)
        rgba = np.dstack([rgb, alpha])
        return Image.fromarray(rgba, "RGBA")
