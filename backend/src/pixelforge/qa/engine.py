"""QA engine (D-013): run detectors, score, and apply the safe repairs.

M9 implements deterministic detection + safe deterministic repair. The diffusion-based
region-repair loop (regenerate only the failing region) is a later milestone; the interface here
(``run`` / ``repair``) is where it will attach.
"""

from __future__ import annotations

import numpy as np
from PIL import Image

from pixelforge.core.scene_graph import Finding, FindingSeverity
from pixelforge.qa.critic import Critic, HeuristicCritic
from pixelforge.qa.models import DetectorContext, QAReport
from pixelforge.qa.registry import DetectorRegistry


class QAEngine:
    def __init__(
        self,
        detectors: DetectorRegistry | None = None,
        critic: Critic | None = None,
        pass_threshold: float = 0.6,
    ) -> None:
        self._detectors = detectors or DetectorRegistry()
        self._critic = critic or HeuristicCritic()
        self._pass_threshold = pass_threshold

    def run(self, image: Image.Image, context: DetectorContext) -> QAReport:
        rgba = np.asarray(image.convert("RGBA"), dtype=np.uint8)
        findings: list[Finding] = []
        for detector in self._detectors.list():
            findings.extend(detector.detect(rgba, context))
        scores, critique = self._critic.evaluate(rgba, context, findings)
        has_error = any(f.severity is FindingSeverity.ERROR for f in findings)
        height, width = rgba.shape[:2]
        return QAReport(
            width=width,
            height=height,
            passed=scores.overall >= self._pass_threshold and not has_error,
            scores=scores,
            findings=findings,
            critique=critique,
        )

    def repair(self, image: Image.Image, context: DetectorContext) -> tuple[Image.Image, QAReport]:
        """Apply every repairable detector's fix, then re-run QA on the result."""
        rgba = np.array(image.convert("RGBA"), dtype=np.uint8)
        for detector in self._detectors.list():
            if detector.repairable and detector.detect(rgba, context):
                rgba = np.ascontiguousarray(detector.repair(rgba, context), dtype=np.uint8)
        repaired = Image.fromarray(rgba, "RGBA")
        return repaired, self.run(repaired, context)
