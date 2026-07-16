"""Palette intelligence: ranking, contrast, CVD, dedup, compression, suggestions (D-012).

Pure and deterministic — no models, no image required. Operates on a :class:`Palette` and returns
typed results, so it runs in CI and can be surfaced directly in the API and the palette panel.
"""

from __future__ import annotations

import numpy as np
from pydantic import BaseModel, Field

from pixelforge.palettes.color_math import (
    CVD_TYPES,
    Lab,
    ciede2000,
    contrast_ratio,
    relative_luminance,
    rgb_to_hue,
    rgb_to_lab,
    simulate_cvd,
)
from pixelforge.palettes.model import RGB, Palette, hex_to_rgb, rgb_to_hex

# Perceptual thresholds (CIEDE2000 units). ~1 = just-noticeable; ~2.3 = "not perceptible" bound.
DUPLICATE_DELTA_E = 2.0
READABILITY_JND = 5.0
CONFUSABLE_DELTA_E = 10.0
MIN_READABLE_CONTRAST = 4.5
_NEUTRAL_CHROMA = 8.0
_RAMP_HUE_TOLERANCE = 35.0


class ColorInfo(BaseModel):
    hex: str
    rgb: RGB
    luminance: float
    hue: float
    lab: tuple[float, float, float]


class ColorPair(BaseModel):
    a: str
    b: str
    delta_e: float
    contrast_ratio: float | None = None


class ContrastReport(BaseModel):
    max_contrast_ratio: float
    min_delta_e: float
    mean_delta_e: float
    low_contrast_pairs: list[ColorPair]


class CvdReport(BaseModel):
    vision: str
    confusable_pairs: list[ColorPair]
    simulated_hex: list[str]


class Suggestion(BaseModel):
    code: str
    severity: str  # "info" | "warning"
    message: str


class PaletteAnalysis(BaseModel):
    palette_id: str
    color_count: int
    colors: list[ColorInfo] = Field(default_factory=list)
    ramps: list[list[str]] = Field(default_factory=list)
    duplicates: list[ColorPair] = Field(default_factory=list)
    contrast: ContrastReport
    cvd: list[CvdReport] = Field(default_factory=list)
    readability_score: float = 0.0
    suggestions: list[Suggestion] = Field(default_factory=list)


class _Entry:
    __slots__ = ("hex", "rgb", "lab", "luminance", "hue", "chroma")

    def __init__(self, color_hex: str) -> None:
        self.hex = color_hex
        self.rgb: RGB = hex_to_rgb(color_hex)
        self.lab: Lab = rgb_to_lab(self.rgb)
        self.luminance = relative_luminance(self.rgb)
        self.hue = rgb_to_hue(self.rgb)
        self.chroma = (self.lab[1] ** 2 + self.lab[2] ** 2) ** 0.5


def _entries(palette: Palette) -> list[_Entry]:
    # Deduplicate identical hex strings while preserving order (a palette may repeat a color).
    seen: set[str] = set()
    entries: list[_Entry] = []
    for color in palette.colors:
        if color not in seen:
            seen.add(color)
            entries.append(_Entry(color))
    return entries


def _info(entry: _Entry) -> ColorInfo:
    return ColorInfo(
        hex=entry.hex,
        rgb=entry.rgb,
        luminance=round(entry.luminance, 4),
        hue=round(entry.hue, 1),
        lab=tuple(round(v, 2) for v in entry.lab),  # type: ignore[arg-type]
    )


def rank_colors(palette: Palette) -> list[ColorInfo]:
    """Colors ordered dark → light (then by hue), each with luminance/hue/Lab."""
    ranked = sorted(_entries(palette), key=lambda e: (e.luminance, e.hue))
    return [_info(entry) for entry in ranked]


def detect_ramps(palette: Palette) -> list[list[str]]:
    """Group colors into ramps: neutrals, then chromatic by hue; each ordered dark→light."""
    entries = _entries(palette)
    neutrals = sorted((e for e in entries if e.chroma < _NEUTRAL_CHROMA), key=lambda e: e.luminance)
    chromatic = sorted((e for e in entries if e.chroma >= _NEUTRAL_CHROMA), key=lambda e: e.hue)

    groups: list[list[_Entry]] = []
    for entry in chromatic:
        if groups and entry.hue - groups[-1][-1].hue <= _RAMP_HUE_TOLERANCE:
            groups[-1].append(entry)
        else:
            groups.append([entry])

    ramps: list[list[str]] = []
    for group in groups:
        if len(group) >= 2:
            ramps.append([e.hex for e in sorted(group, key=lambda e: e.luminance)])
    if len(neutrals) >= 2:
        ramps.insert(0, [e.hex for e in neutrals])
    return ramps


def find_duplicates(palette: Palette, threshold: float = DUPLICATE_DELTA_E) -> list[ColorPair]:
    """Pairs of colors closer than ``threshold`` in CIEDE2000 (perceptually near-identical)."""
    entries = _entries(palette)
    pairs: list[ColorPair] = []
    for i in range(len(entries)):
        for j in range(i + 1, len(entries)):
            delta = ciede2000(entries[i].lab, entries[j].lab)
            if delta < threshold:
                pairs.append(ColorPair(a=entries[i].hex, b=entries[j].hex, delta_e=round(delta, 2)))
    return pairs


def _contrast_report(entries: list[_Entry]) -> ContrastReport:
    if len(entries) < 2:
        return ContrastReport(
            max_contrast_ratio=1.0, min_delta_e=0.0, mean_delta_e=0.0, low_contrast_pairs=[]
        )
    max_ratio = 1.0
    deltas: list[float] = []
    low: list[ColorPair] = []
    for i in range(len(entries)):
        for j in range(i + 1, len(entries)):
            ratio = contrast_ratio(entries[i].rgb, entries[j].rgb)
            delta = ciede2000(entries[i].lab, entries[j].lab)
            max_ratio = max(max_ratio, ratio)
            deltas.append(delta)
            if delta < READABILITY_JND:
                low.append(
                    ColorPair(
                        a=entries[i].hex,
                        b=entries[j].hex,
                        delta_e=round(delta, 2),
                        contrast_ratio=round(ratio, 2),
                    )
                )
    return ContrastReport(
        max_contrast_ratio=round(max_ratio, 2),
        min_delta_e=round(min(deltas), 2),
        mean_delta_e=round(sum(deltas) / len(deltas), 2),
        low_contrast_pairs=low,
    )


def cvd_reports(palette: Palette) -> list[CvdReport]:
    """For each CVD type, colors that were distinct but become confusable under simulation."""
    entries = _entries(palette)
    originals = [e.rgb for e in entries]
    reports: list[CvdReport] = []
    for vision in CVD_TYPES:
        simulated = simulate_cvd(originals, vision)
        sim_lab = [rgb_to_lab(c) for c in simulated]
        confusable: list[ColorPair] = []
        for i in range(len(entries)):
            for j in range(i + 1, len(entries)):
                before = ciede2000(entries[i].lab, entries[j].lab)
                after = ciede2000(sim_lab[i], sim_lab[j])
                if before >= CONFUSABLE_DELTA_E and after < CONFUSABLE_DELTA_E:
                    confusable.append(
                        ColorPair(a=entries[i].hex, b=entries[j].hex, delta_e=round(after, 2))
                    )
        reports.append(
            CvdReport(
                vision=vision,
                confusable_pairs=confusable,
                simulated_hex=[rgb_to_hex(c) for c in simulated],
            )
        )
    return reports


def _readability_score(entries: list[_Entry], contrast: ContrastReport) -> float:
    if len(entries) < 2:
        return 1.0
    total = 0
    distinct = 0
    for i in range(len(entries)):
        for j in range(i + 1, len(entries)):
            total += 1
            if ciede2000(entries[i].lab, entries[j].lab) >= READABILITY_JND:
                distinct += 1
    distinct_fraction = distinct / total if total else 1.0
    contrast_norm = min(contrast.max_contrast_ratio / 21.0, 1.0)
    return round(0.5 * distinct_fraction + 0.5 * contrast_norm, 3)


def compress_palette(
    palette: Palette, target_colors: int, palette_id: str | None = None
) -> Palette:
    """Reduce the palette to ``target_colors`` with minimal perceptual loss (k-means in CIELAB).

    Representatives are chosen from the *original* colors (nearest to each cluster centroid), so the
    result stays faithful to the artist's chosen hues rather than inventing new ones.
    """
    entries = _entries(palette)
    if target_colors < 1:
        raise ValueError("target_colors must be >= 1")
    if len(entries) <= target_colors:
        return _rebuild(palette, [e.hex for e in entries], palette_id, suffix="dedup")

    points = np.array([e.lab for e in entries], dtype=np.float64)
    order = np.argsort(points[:, 0])  # deterministic init: spread along lightness
    centroids = points[order[np.linspace(0, len(entries) - 1, target_colors).astype(int)]].copy()

    assignments = np.zeros(len(entries), dtype=int)
    for _ in range(50):
        distances = np.linalg.norm(points[:, None, :] - centroids[None, :, :], axis=-1)
        new_assignments = np.argmin(distances, axis=-1)
        if np.array_equal(new_assignments, assignments) and _ > 0:
            break
        assignments = new_assignments
        for k in range(target_colors):
            members = points[assignments == k]
            if len(members) > 0:
                centroids[k] = members.mean(axis=0)

    chosen: list[str] = []
    for k in range(target_colors):
        member_indices = np.where(assignments == k)[0]
        if len(member_indices) == 0:
            continue
        centroid = centroids[k]
        best = min(member_indices, key=lambda idx: float(np.linalg.norm(points[idx] - centroid)))
        if entries[best].hex not in chosen:
            chosen.append(entries[best].hex)
    ordered = sorted(chosen, key=lambda h: relative_luminance(hex_to_rgb(h)))
    return _rebuild(palette, ordered, palette_id, suffix="compressed")


def _rebuild(palette: Palette, colors: list[str], palette_id: str | None, suffix: str) -> Palette:
    return Palette(
        id=palette_id or f"{palette.id}-{suffix}",
        name=f"{palette.name} ({suffix}, {len(colors)} colors)",
        colors=colors,
    )


def simulate_cvd_palette(
    palette: Palette, vision: str, severity: float = 1.0, palette_id: str | None = None
) -> Palette:
    """Return a new palette as it would appear under the given color-vision deficiency."""
    simulated = simulate_cvd([hex_to_rgb(c) for c in palette.colors], vision, severity)
    return Palette(
        id=palette_id or f"{palette.id}-{vision}",
        name=f"{palette.name} ({vision})",
        colors=[rgb_to_hex(c) for c in simulated],
    )


def _suggestions(
    entries: list[_Entry],
    duplicates: list[ColorPair],
    contrast: ContrastReport,
    cvd: list[CvdReport],
    ramps: list[list[str]],
    readability: float,
) -> list[Suggestion]:
    out: list[Suggestion] = []
    if duplicates:
        out.append(
            Suggestion(
                code="duplicates",
                severity="warning",
                message=f"{len(duplicates)} near-duplicate color pair(s); consider merging them.",
            )
        )
    if len(entries) >= 2 and contrast.max_contrast_ratio < MIN_READABLE_CONTRAST:
        out.append(
            Suggestion(
                code="low-contrast",
                severity="warning",
                message=(
                    f"Low overall contrast (best ratio {contrast.max_contrast_ratio}:1); add a "
                    "darker or lighter color for readability."
                ),
            )
        )
    for report in cvd:
        if report.confusable_pairs:
            out.append(
                Suggestion(
                    code=f"cvd-{report.vision}",
                    severity="warning",
                    message=(
                        f"{len(report.confusable_pairs)} color pair(s) become hard to tell apart "
                        f"under {report.vision}."
                    ),
                )
            )
    if len(entries) >= 4 and not ramps:
        out.append(
            Suggestion(
                code="no-ramp",
                severity="info",
                message="No clear shading ramp detected; group colors into dark→light ramps.",
            )
        )
    if not out and readability >= 0.7:
        out.append(
            Suggestion(
                code="looks-good",
                severity="info",
                message="Palette reads well: strong contrast and distinct colors.",
            )
        )
    return out


def analyze_palette(palette: Palette) -> PaletteAnalysis:
    """Full analysis of a palette: ranking, ramps, duplicates, contrast, CVD, and suggestions."""
    entries = _entries(palette)
    contrast = _contrast_report(entries)
    duplicates = find_duplicates(palette)
    ramps = detect_ramps(palette)
    cvd = cvd_reports(palette)
    readability = _readability_score(entries, contrast)
    return PaletteAnalysis(
        palette_id=palette.id,
        color_count=len(entries),
        colors=[_info(e) for e in sorted(entries, key=lambda e: (e.luminance, e.hue))],
        ramps=ramps,
        duplicates=duplicates,
        contrast=contrast,
        cvd=cvd,
        readability_score=readability,
        suggestions=_suggestions(entries, duplicates, contrast, cvd, ramps, readability),
    )
