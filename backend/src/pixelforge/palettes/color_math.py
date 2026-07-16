"""Color science for palette intelligence (D-012).

Pure, deterministic, model-free. Everything here operates on sRGB ``(r, g, b)`` byte tuples and is
exact and unit-testable: sRGB↔linear↔XYZ↔CIELAB conversions, WCAG relative luminance and contrast
ratio, CIEDE2000 perceptual difference, hue, and Machado-2009 color-vision-deficiency simulation.
"""

from __future__ import annotations

import math

import numpy as np

from pixelforge.palettes.model import RGB

Lab = tuple[float, float, float]

# sRGB (D65) → XYZ. Row 1 is the luminance (Y) response, i.e. WCAG relative luminance weights.
_RGB_TO_XYZ = (
    (0.4124564, 0.3575761, 0.1804375),
    (0.2126729, 0.7151522, 0.0721750),
    (0.0193339, 0.1191920, 0.9503041),
)
# CIE D65 reference white.
_WHITE = (0.95047, 1.0, 1.08883)
# CIELAB constants (CIE standard).
_EPSILON = 216.0 / 24389.0
_KAPPA = 24389.0 / 27.0

# Machado et al. (2009) dichromacy matrices (severity 1.0), applied in linear RGB.
_MACHADO_SEVERE: dict[str, tuple[tuple[float, float, float], ...]] = {
    "protanopia": (
        (0.152286, 1.052583, -0.204868),
        (0.114503, 0.786281, 0.099216),
        (-0.003882, -0.048116, 1.051998),
    ),
    "deuteranopia": (
        (0.367322, 0.860646, -0.227968),
        (0.280085, 0.672501, 0.047413),
        (-0.011820, 0.042940, 0.968881),
    ),
    "tritanopia": (
        (1.255528, -0.076749, -0.178779),
        (-0.078411, 0.930809, 0.147602),
        (0.004733, 0.691367, 0.303900),
    ),
}

CVD_TYPES: tuple[str, ...] = ("protanopia", "deuteranopia", "tritanopia")


def _srgb_to_linear(channel: float) -> float:
    """Linearize one sRGB channel in [0, 1]."""
    return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4


def _linear_to_srgb(channel: float) -> float:
    channel = min(max(channel, 0.0), 1.0)
    return channel * 12.92 if channel <= 0.0031308 else 1.055 * channel ** (1 / 2.4) - 0.055


def _linear_rgb(rgb: RGB) -> tuple[float, float, float]:
    return (
        _srgb_to_linear(rgb[0] / 255.0),
        _srgb_to_linear(rgb[1] / 255.0),
        _srgb_to_linear(rgb[2] / 255.0),
    )


def relative_luminance(rgb: RGB) -> float:
    """WCAG relative luminance (0 = black, 1 = white)."""
    r, g, b = _linear_rgb(rgb)
    row = _RGB_TO_XYZ[1]
    return row[0] * r + row[1] * g + row[2] * b


def contrast_ratio(a: RGB, b: RGB) -> float:
    """WCAG contrast ratio in [1, 21]."""
    lighter, darker = sorted((relative_luminance(a), relative_luminance(b)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def rgb_to_lab(rgb: RGB) -> Lab:
    """Convert an sRGB byte tuple to CIELAB (D65)."""
    r, g, b = _linear_rgb(rgb)
    xyz = tuple(row[0] * r + row[1] * g + row[2] * b for row in _RGB_TO_XYZ)
    fx, fy, fz = (_lab_f(component / white) for component, white in zip(xyz, _WHITE, strict=True))
    return (116.0 * fy - 16.0, 500.0 * (fx - fy), 200.0 * (fy - fz))


def _lab_f(t: float) -> float:
    return t ** (1.0 / 3.0) if t > _EPSILON else (_KAPPA * t + 16.0) / 116.0


def rgb_to_hue(rgb: RGB) -> float:
    """Hue angle in degrees [0, 360)."""
    r, g, b = (c / 255.0 for c in rgb)
    high, low = max(r, g, b), min(r, g, b)
    chroma = high - low
    if chroma == 0:
        return 0.0
    if high == r:
        hue = ((g - b) / chroma) % 6.0
    elif high == g:
        hue = (b - r) / chroma + 2.0
    else:
        hue = (r - g) / chroma + 4.0
    return (hue * 60.0) % 360.0


def ciede2000(lab1: Lab, lab2: Lab) -> float:
    """CIEDE2000 perceptual color difference (Sharma et al. formulation)."""
    l1, a1, b1 = lab1
    l2, a2, b2 = lab2

    c1 = math.hypot(a1, b1)
    c2 = math.hypot(a2, b2)
    c_bar = (c1 + c2) / 2.0
    g = 0.5 * (1.0 - math.sqrt(c_bar**7 / (c_bar**7 + 25.0**7))) if c_bar > 0 else 0.0

    a1p, a2p = (1.0 + g) * a1, (1.0 + g) * a2
    c1p, c2p = math.hypot(a1p, b1), math.hypot(a2p, b2)
    h1p, h2p = _hue_deg(b1, a1p), _hue_deg(b2, a2p)

    dlp = l2 - l1
    dcp = c2p - c1p
    dhp = _delta_h(h1p, h2p, c1p, c2p)
    d_bighp = 2.0 * math.sqrt(c1p * c2p) * math.sin(math.radians(dhp) / 2.0)

    lbarp = (l1 + l2) / 2.0
    cbarp = (c1p + c2p) / 2.0
    hbarp = _mean_hue(h1p, h2p, c1p, c2p)

    t = (
        1.0
        - 0.17 * math.cos(math.radians(hbarp - 30.0))
        + 0.24 * math.cos(math.radians(2.0 * hbarp))
        + 0.32 * math.cos(math.radians(3.0 * hbarp + 6.0))
        - 0.20 * math.cos(math.radians(4.0 * hbarp - 63.0))
    )
    dtheta = 30.0 * math.exp(-(((hbarp - 275.0) / 25.0) ** 2))
    rc = 2.0 * math.sqrt(cbarp**7 / (cbarp**7 + 25.0**7)) if cbarp > 0 else 0.0
    sl = 1.0 + (0.015 * (lbarp - 50.0) ** 2) / math.sqrt(20.0 + (lbarp - 50.0) ** 2)
    sc = 1.0 + 0.045 * cbarp
    sh = 1.0 + 0.015 * cbarp * t
    rt = -math.sin(math.radians(2.0 * dtheta)) * rc

    return math.sqrt(
        (dlp / sl) ** 2 + (dcp / sc) ** 2 + (d_bighp / sh) ** 2 + rt * (dcp / sc) * (d_bighp / sh)
    )


def _hue_deg(b: float, ap: float) -> float:
    if ap == 0.0 and b == 0.0:
        return 0.0
    return math.degrees(math.atan2(b, ap)) % 360.0


def _delta_h(h1p: float, h2p: float, c1p: float, c2p: float) -> float:
    if c1p * c2p == 0.0:
        return 0.0
    diff = h2p - h1p
    if diff > 180.0:
        diff -= 360.0
    elif diff < -180.0:
        diff += 360.0
    return diff


def _mean_hue(h1p: float, h2p: float, c1p: float, c2p: float) -> float:
    if c1p * c2p == 0.0:
        return h1p + h2p
    if abs(h1p - h2p) <= 180.0:
        return (h1p + h2p) / 2.0
    if h1p + h2p < 360.0:
        return (h1p + h2p + 360.0) / 2.0
    return (h1p + h2p - 360.0) / 2.0


def _machado_matrix(vision: str, severity: float) -> np.ndarray:
    if vision not in _MACHADO_SEVERE:
        raise ValueError(f"unknown vision type: {vision}; expected one of {CVD_TYPES}")
    severity = min(max(severity, 0.0), 1.0)
    severe = np.array(_MACHADO_SEVERE[vision], dtype=np.float64)
    # Machado publishes per-severity matrices; interpolating toward identity is a practical
    # approximation. severity 1.0 (the default) uses the exact published dichromacy matrix.
    return (1.0 - severity) * np.eye(3) + severity * severe


def simulate_cvd(colors: list[RGB], vision: str, severity: float = 1.0) -> list[RGB]:
    """Simulate how ``colors`` appear under a color-vision deficiency (Machado 2009)."""
    if not colors:
        return []
    matrix = _machado_matrix(vision, severity)
    linear = np.array([_linear_rgb(c) for c in colors], dtype=np.float64)  # (n, 3)
    simulated = np.clip(linear @ matrix.T, 0.0, 1.0)
    out: list[RGB] = []
    for row in simulated:
        r = round(_linear_to_srgb(float(row[0])) * 255.0)
        g = round(_linear_to_srgb(float(row[1])) * 255.0)
        b = round(_linear_to_srgb(float(row[2])) * 255.0)
        out.append((r, g, b))
    return out
