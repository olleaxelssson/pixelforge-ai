"""QA-gated repair loop (D-013 Layer 2): the critique → repair half of the pipeline.

Layer 1 (``QAEngine``) detects defects and applies *safe, global* deterministic repairs. Layer 2
closes the loop: run QA, and while the sprite still fails, **regenerate only the failing regions**
and re-score — accepting a candidate only when it *strictly improves* the QA score and adds no new
errors. The loop is bounded (``max_iterations``) and monotonic, so it always terminates.

Region regeneration is pluggable via :class:`RegionRegenerator`:

- :class:`DeterministicInpaintRegenerator` — a median denoise (+ optional palette snap) scoped to
  the failing mask. Deterministic, runs in CI, and reliably cleans localized noise Layer 1 leaves.
- :class:`BackendRegionRegenerator` — the *real* path: img2img on the failing crop through a
  ``GenerationBackend``. Same interface, no other code changes; works with the mock backend too.

The loop touches only masked pixels; everything outside the failing mask is guaranteed unchanged.
"""

from __future__ import annotations

from typing import Protocol

import numpy as np
from PIL import Image
from pydantic import BaseModel, Field

from pixelforge.core.scene_graph import FindingSeverity
from pixelforge.generation.backends.base import DiffusionSpec, GenerationBackend
from pixelforge.qa.engine import QAEngine
from pixelforge.qa.models import DetectorContext, QAReport

# Minimum overall-score gain for a candidate to be accepted (guards against churn/regressions).
_MIN_IMPROVEMENT = 1e-4


class RegionRegenerator(Protocol):
    """Regenerate the pixels of ``rgba`` where ``mask`` is True; leave all others untouched."""

    def regenerate(
        self, rgba: np.ndarray, mask: np.ndarray, context: DetectorContext
    ) -> np.ndarray: ...


class RepairAttempt(BaseModel):
    iteration: int
    regions: int  # failing findings targeted this pass
    pixels: int  # pixels in the failing mask
    overall_before: float
    overall_after: float
    accepted: bool


class RepairLoopReport(BaseModel):
    iterations: int
    improved: bool
    initial: QAReport
    final: QAReport
    attempts: list[RepairAttempt] = Field(default_factory=list)


def _error_count(report: QAReport) -> int:
    return sum(1 for f in report.findings if f.severity is FindingSeverity.ERROR)


def _failing_mask(report: QAReport) -> np.ndarray:
    """Union of the bounding boxes of non-advisory findings that carry a region."""
    mask = np.zeros((report.height, report.width), dtype=bool)
    for finding in report.findings:
        region = finding.region
        if region is None or finding.severity is FindingSeverity.INFO:
            continue
        x0 = max(0, region.x)
        y0 = max(0, region.y)
        x1 = min(report.width, region.x + max(1, region.width))
        y1 = min(report.height, region.y + max(1, region.height))
        if x1 > x0 and y1 > y0:
            mask[y0:y1, x0:x1] = True
    return mask


def _targetable_findings(report: QAReport) -> int:
    return sum(
        1
        for f in report.findings
        if f.region is not None and f.severity is not FindingSeverity.INFO
    )


def _median_3x3(rgba: np.ndarray) -> np.ndarray:
    """Per-channel 3x3 median (edge-replicated). Removes speckle; idempotent on flat areas."""
    padded = np.pad(rgba, ((1, 1), (1, 1), (0, 0)), mode="edge").astype(np.int16)
    windows = [
        padded[dy : dy + rgba.shape[0], dx : dx + rgba.shape[1], :]
        for dy in range(3)
        for dx in range(3)
    ]
    return np.median(np.stack(windows, axis=0), axis=0).astype(np.uint8)


def _snap_to_palette(rgb: np.ndarray, palette: list[tuple[int, int, int]]) -> np.ndarray:
    swatches = np.asarray(palette, dtype=np.int16)
    flat = rgb.reshape(-1, 3).astype(np.int16)
    distances = ((flat[:, None, :] - swatches[None, :, :]) ** 2).sum(axis=2)
    nearest = distances.argmin(axis=1)
    return swatches[nearest].astype(np.uint8).reshape(rgb.shape)


class DeterministicInpaintRegenerator:
    """Median-denoise the failing mask (then snap to the locked palette, if any).

    A 3x3 median removes isolated speckle — floaters drop out (their alpha median is 0), interior
    noise collapses to the surrounding color — while leaving clean, flat regions untouched. That
    idempotence on clean pixels is what makes the surrounding loop converge.
    """

    def regenerate(
        self, rgba: np.ndarray, mask: np.ndarray, context: DetectorContext
    ) -> np.ndarray:
        out = rgba.copy()
        candidate = _median_3x3(rgba)
        if context.palette:
            candidate[..., :3] = _snap_to_palette(candidate[..., :3], context.palette)
        out[mask] = candidate[mask]
        return out


class BackendRegionRegenerator:
    """Real region regeneration: img2img on the failing crop via a ``GenerationBackend``.

    The failing mask's bounding box is sent to the backend as a reference image; the returned patch
    is resized back and composited in — only masked pixels change. Uses the same interface as the
    deterministic regenerator, so the loop is backend-agnostic (and works with the mock backend).
    """

    def __init__(self, backend: GenerationBackend, spec: DiffusionSpec) -> None:
        self._backend = backend
        self._spec = spec

    def regenerate(
        self, rgba: np.ndarray, mask: np.ndarray, context: DetectorContext
    ) -> np.ndarray:
        ys, xs = np.nonzero(mask)
        if len(ys) == 0:
            return rgba
        y0, y1 = int(ys.min()), int(ys.max()) + 1
        x0, x1 = int(xs.min()), int(xs.max()) + 1
        crop = Image.fromarray(rgba[y0:y1, x0:x1], "RGBA")

        spec = DiffusionSpec(
            prompt=self._spec.prompt,
            negative_prompt=self._spec.negative_prompt,
            resolution=max(self._spec.resolution // 4, 64),
            steps=self._spec.steps,
            seed=self._spec.seed + 1,
            batch_size=1,
            reference_image=crop.convert("RGB"),
            reference_strength=max(self._spec.reference_strength, 0.5),
        )
        generated = self._backend.generate(spec, lambda _fraction: None)[0]
        patch = np.asarray(
            generated.convert("RGBA").resize((x1 - x0, y1 - y0), Image.Resampling.NEAREST),
            dtype=np.uint8,
        )

        out = rgba.copy()
        crop_mask = mask[y0:y1, x0:x1]
        region = out[y0:y1, x0:x1]
        region[crop_mask] = patch[crop_mask]
        out[y0:y1, x0:x1] = region
        return out


class RepairLoop:
    """Bounded QA-gated repair loop over a :class:`RegionRegenerator`."""

    def __init__(
        self,
        engine: QAEngine | None = None,
        regenerator: RegionRegenerator | None = None,
        max_iterations: int = 2,
    ) -> None:
        self._engine = engine or QAEngine()
        self._regenerator = regenerator or DeterministicInpaintRegenerator()
        self._max_iterations = max(1, max_iterations)

    def run(
        self, image: Image.Image, context: DetectorContext
    ) -> tuple[Image.Image, RepairLoopReport]:
        rgba = np.asarray(image.convert("RGBA"), dtype=np.uint8)
        initial = self._engine.run(image, context)
        current = initial
        attempts: list[RepairAttempt] = []

        for iteration in range(1, self._max_iterations + 1):
            if current.passed:
                break
            mask = _failing_mask(current)
            if not mask.any():
                break  # only advisory findings remain — nothing safe to regenerate

            candidate_rgba = self._regenerator.regenerate(rgba, mask, context)
            # Enforce the contract: pixels outside the mask must be identical.
            candidate_rgba = np.where(mask[..., None], candidate_rgba, rgba)
            candidate_image = Image.fromarray(candidate_rgba.astype(np.uint8), "RGBA")
            candidate = self._engine.run(candidate_image, context)

            gain = candidate.scores.overall - current.scores.overall
            accepted = gain > _MIN_IMPROVEMENT and _error_count(candidate) <= _error_count(current)
            attempts.append(
                RepairAttempt(
                    iteration=iteration,
                    regions=_targetable_findings(current),
                    pixels=int(mask.sum()),
                    overall_before=current.scores.overall,
                    overall_after=candidate.scores.overall,
                    accepted=accepted,
                )
            )
            if not accepted:
                break  # no progress — stop rather than churn
            rgba = candidate_rgba.astype(np.uint8)
            current = candidate

        final_image = Image.fromarray(rgba, "RGBA")
        return final_image, RepairLoopReport(
            iterations=len(attempts),
            improved=current.scores.overall > initial.scores.overall,
            initial=initial,
            final=current,
            attempts=attempts,
        )
