/** Pure tiling-preview helpers (M22) — unit-tested; the React panel is not.
 *
 * Mirrors the backend `generation.tileize.seam_metrics`: measures how far a sprite's opposite
 * edges are from matching, so the UI can show a live seamlessness readout for the tiling preview.
 */

export interface SeamScore {
  /** Left/right edge discontinuity, 0 (seamless) → 1. */
  horizontal: number;
  /** Top/bottom edge discontinuity, 0 (seamless) → 1. */
  vertical: number;
  /** Overall seamlessness in [0, 1] (1 = perfectly seamless). */
  overall: number;
}

/** Compute the edge-wrap seam score from raw RGBA pixels (`width*height*4`, row-major). */
export function seamScore(pixels: Uint8ClampedArray, width: number, height: number): SeamScore {
  const at = (x: number, y: number, c: number) => pixels[(y * width + x) * 4 + c];

  let hSum = 0;
  for (let y = 0; y < height; y++) {
    for (let c = 0; c < 3; c++) hSum += Math.abs(at(0, y, c) - at(width - 1, y, c));
  }
  let vSum = 0;
  for (let x = 0; x < width; x++) {
    for (let c = 0; c < 3; c++) vSum += Math.abs(at(x, 0, c) - at(x, height - 1, c));
  }

  const horizontal = height > 0 ? hSum / (height * 3 * 255) : 0;
  const vertical = width > 0 ? vSum / (width * 3 * 255) : 0;
  return { horizontal, vertical, overall: 1 - Math.max(horizontal, vertical) };
}

export interface SeamBadge {
  percent: number;
  ok: boolean;
  label: string;
}

/** A seamlessness badge: percentage + whether it clears the "seamless enough" bar. */
export function seamBadge(score: SeamScore, threshold = 0.92): SeamBadge {
  const percent = Math.round(score.overall * 100);
  const ok = score.overall >= threshold;
  return { percent, ok, label: ok ? "seamless" : "visible seam" };
}
