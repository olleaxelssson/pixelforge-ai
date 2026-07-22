import { describe, expect, it } from "vitest";

import { seamBadge, seamScore } from "./tileView";

/** Build an RGBA buffer from a per-pixel color function. */
function makePixels(
  width: number,
  height: number,
  color: (x: number, y: number) => [number, number, number],
): Uint8ClampedArray {
  const pixels = new Uint8ClampedArray(width * height * 4);
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      const [r, g, b] = color(x, y);
      const i = (y * width + x) * 4;
      pixels[i] = r;
      pixels[i + 1] = g;
      pixels[i + 2] = b;
      pixels[i + 3] = 255;
    }
  }
  return pixels;
}

describe("seamScore", () => {
  it("is perfectly seamless for a flat image", () => {
    const pixels = makePixels(8, 8, () => [100, 120, 140]);
    const score = seamScore(pixels, 8, 8);
    expect(score.horizontal).toBe(0);
    expect(score.vertical).toBe(0);
    expect(score.overall).toBe(1);
  });

  it("detects a horizontal seam (left edge differs from right edge)", () => {
    // left column black, right column white → maximal left/right discontinuity.
    const pixels = makePixels(4, 4, (x) => (x === 0 ? [0, 0, 0] : x === 3 ? [255, 255, 255] : [128, 128, 128]));
    const score = seamScore(pixels, 4, 4);
    expect(score.horizontal).toBeCloseTo(1, 5);
    expect(score.vertical).toBe(0);
    expect(score.overall).toBeCloseTo(0, 5);
  });

  it("detects a vertical seam (top row differs from bottom row)", () => {
    const pixels = makePixels(4, 4, (_x, y) => (y === 0 ? [0, 0, 0] : y === 3 ? [255, 255, 255] : [128, 128, 128]));
    const score = seamScore(pixels, 4, 4);
    expect(score.vertical).toBeCloseTo(1, 5);
    expect(score.horizontal).toBe(0);
  });
});

describe("seamBadge", () => {
  it("marks a seamless score ok", () => {
    const badge = seamBadge({ horizontal: 0, vertical: 0, overall: 1 });
    expect(badge).toEqual({ percent: 100, ok: true, label: "seamless" });
  });

  it("marks a seam below threshold not ok", () => {
    const badge = seamBadge({ horizontal: 0.3, vertical: 0.1, overall: 0.7 });
    expect(badge.ok).toBe(false);
    expect(badge.label).toBe("visible seam");
    expect(badge.percent).toBe(70);
  });
});
