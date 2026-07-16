"""Color-math tests (D-012): validated against known WCAG / CIEDE2000 / CVD reference values."""

from __future__ import annotations

import pytest

from pixelforge.palettes.color_math import (
    ciede2000,
    contrast_ratio,
    relative_luminance,
    rgb_to_hue,
    rgb_to_lab,
    simulate_cvd,
)


def test_contrast_black_white_is_21() -> None:
    assert contrast_ratio((0, 0, 0), (255, 255, 255)) == pytest.approx(21.0)


def test_contrast_symmetric_and_min_one() -> None:
    assert contrast_ratio((10, 20, 30), (10, 20, 30)) == pytest.approx(1.0)
    assert contrast_ratio((0, 0, 0), (255, 255, 255)) == contrast_ratio((255, 255, 255), (0, 0, 0))


def test_luminance_bounds() -> None:
    assert relative_luminance((0, 0, 0)) == pytest.approx(0.0)
    assert relative_luminance((255, 255, 255)) == pytest.approx(1.0)


def test_lab_reference_points() -> None:
    assert rgb_to_lab((255, 255, 255)) == pytest.approx((100.0, 0.0, 0.0), abs=0.01)
    assert rgb_to_lab((0, 0, 0))[0] == pytest.approx(0.0, abs=0.01)


def test_ciede2000_reference_pairs() -> None:
    # From the Sharma et al. CIEDE2000 verification dataset.
    assert ciede2000((50.0, 2.6772, -79.7751), (50.0, 0.0, -82.7485)) == pytest.approx(
        2.0425, abs=1e-3
    )
    assert ciede2000((50.0, 2.5, 0.0), (73.0, 25.0, -18.0)) == pytest.approx(27.1492, abs=1e-3)


def test_ciede2000_zero_for_identical() -> None:
    lab = rgb_to_lab((123, 45, 200))
    assert ciede2000(lab, lab) == pytest.approx(0.0, abs=1e-9)


def test_hue_primary_colors() -> None:
    assert rgb_to_hue((255, 0, 0)) == pytest.approx(0.0)
    assert rgb_to_hue((0, 255, 0)) == pytest.approx(120.0)
    assert rgb_to_hue((0, 0, 255)) == pytest.approx(240.0)
    assert rgb_to_hue((128, 128, 128)) == pytest.approx(0.0)  # achromatic


def test_deuteranopia_collapses_red_green() -> None:
    red, green = (208, 40, 40), (40, 160, 40)
    before = ciede2000(rgb_to_lab(red), rgb_to_lab(green))
    sim_red, sim_green = simulate_cvd([red, green], "deuteranopia")
    after = ciede2000(rgb_to_lab(sim_red), rgb_to_lab(sim_green))
    assert before > 30.0
    assert after < before / 2.0


def test_simulate_cvd_severity_zero_is_near_identity() -> None:
    colors = [(200, 30, 30), (30, 160, 30), (30, 30, 200)]
    out = simulate_cvd(colors, "deuteranopia", severity=0.0)
    for original, result in zip(colors, out, strict=True):
        assert all(abs(a - b) <= 1 for a, b in zip(original, result, strict=True))


def test_simulate_cvd_unknown_vision_raises() -> None:
    with pytest.raises(ValueError, match="unknown vision"):
        simulate_cvd([(0, 0, 0)], "nope")
