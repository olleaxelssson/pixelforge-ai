"""Deterministic mock critic backend (D-013).

Stands in for a real VLM so the semantic-critic path runs in CI with no weights. ``appeal`` is a
genuine, image-derived signal (palette readability + a silhouette-coverage band); ``subject_match``
is a deterministic, subject-and-image-dependent proxy (a hash agreement) — plausible in shape, not
real understanding. Same inputs → same Critique. A real model replaces this behind the same
interface (see :mod:`vlm`).
"""

from __future__ import annotations

import hashlib

import numpy as np

from pixelforge.palettes.analysis import analyze_palette
from pixelforge.palettes.model import Palette, rgb_to_hex
from pixelforge.qa.critic_backends.base import CriticBackend
from pixelforge.qa.models import Critique, DetectorContext

_COLOR_CAP = 32


def _bit_agreement(a: bytes, b: bytes) -> float:
    """Fraction of agreeing bits between two 4-byte digests → [0, 1]."""
    x = int.from_bytes(a[:4], "little") ^ int.from_bytes(b[:4], "little")
    return 1.0 - bin(x).count("1") / 32.0


class MockCriticBackend(CriticBackend):
    name = "mock"

    def assess(self, rgba: np.ndarray, context: DetectorContext) -> Critique:
        opaque = rgba[..., 3] > 0
        coverage = float(opaque.mean())

        # Appeal: real signal — palette readability, docked when the silhouette barely/overly fills.
        rgb = rgba[opaque][:, :3]
        if len(rgb) == 0:
            return Critique(
                backend=self.name,
                subject=context.subject,
                subject_match=0.0,
                appeal=0.0,
                verdict="empty sprite",
                notes=["no opaque pixels to judge"],
            )
        colors, counts = np.unique(rgb, axis=0, return_counts=True)
        order = np.argsort(counts)[::-1][:_COLOR_CAP]
        hexes = [rgb_to_hex((int(c[0]), int(c[1]), int(c[2]))) for c in colors[order]]
        readability = analyze_palette(Palette(id="_c", name="c", colors=hexes)).readability_score
        band = 1.0 if 0.15 <= coverage <= 0.75 else 0.6
        appeal = round(min(1.0, readability * band), 3)

        # Subject match: deterministic in (subject, image); neutral when no subject was given.
        notes: list[str] = []
        if context.subject:
            img_sig = hashlib.sha256(np.ascontiguousarray(rgba[::2, ::2]).tobytes()).digest()
            subj_sig = hashlib.sha256(context.subject.strip().lower().encode()).digest()
            subject_match = round(_bit_agreement(img_sig, subj_sig), 3)
            verdict = (
                f"reads clearly as {context.subject!r}"
                if subject_match >= 0.6
                else f"subject {context.subject!r} is ambiguous"
            )
        else:
            subject_match = 0.5
            verdict = "no intended subject given"
            notes.append("pass a subject to enable semantic judgment")

        if coverage < 0.1:
            notes.append("subject barely fills the frame")
        elif coverage > 0.85:
            notes.append("subject fills the whole frame — weak silhouette")
        if appeal < 0.5:
            notes.append("low color readability")

        return Critique(
            backend=self.name,
            subject=context.subject,
            subject_match=subject_match,
            appeal=appeal,
            verdict=verdict,
            notes=notes,
        )
