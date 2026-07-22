/** Pure helpers for the paintable Tileset grid (M23) — unit-tested; the React panel is not. */

/** A fresh ``size × size`` paint grid, every cell painted with variant 0 (the base tile). */
export function createGrid(size: number): number[] {
  return new Array(Math.max(0, size) * Math.max(0, size)).fill(0);
}

/** Return a new grid with ``index`` painted to ``variant`` (immutable). */
export function paintCell(grid: number[], index: number, variant: number): number[] {
  if (index < 0 || index >= grid.length) return grid;
  const next = grid.slice();
  next[index] = variant;
  return next;
}

/** The next variant when a cell is clicked to cycle through the family (wraps around). */
export function cycleVariant(current: number, variantCount: number): number {
  if (variantCount <= 0) return 0;
  return (current + 1) % variantCount;
}

export interface CoherenceBadge {
  percent: number;
  ok: boolean;
  label: string;
}

/** A coherence badge from the min edge-consistency across the set (does every tile abut cleanly?). */
export function coherenceBadge(minEdgeConsistency: number, threshold = 0.9): CoherenceBadge {
  const percent = Math.round(minEdgeConsistency * 100);
  const ok = minEdgeConsistency >= threshold;
  return { percent, ok, label: ok ? "tiles abut cleanly" : "edges mismatch" };
}
