import { describe, expect, it } from "vitest";

import { coherenceBadge, createGrid, cycleVariant, paintCell } from "./tilesetView";

describe("createGrid", () => {
  it("makes an N×N grid of the base variant", () => {
    expect(createGrid(3)).toEqual([0, 0, 0, 0, 0, 0, 0, 0, 0]);
    expect(createGrid(0)).toEqual([]);
  });
});

describe("paintCell", () => {
  it("paints a cell without mutating the original grid", () => {
    const grid = createGrid(2);
    const next = paintCell(grid, 1, 3);
    expect(next).toEqual([0, 3, 0, 0]);
    expect(grid).toEqual([0, 0, 0, 0]); // unchanged
  });

  it("ignores out-of-range indices", () => {
    const grid = createGrid(2);
    expect(paintCell(grid, 9, 2)).toBe(grid);
    expect(paintCell(grid, -1, 2)).toBe(grid);
  });
});

describe("cycleVariant", () => {
  it("advances and wraps around the family", () => {
    expect(cycleVariant(0, 4)).toBe(1);
    expect(cycleVariant(3, 4)).toBe(0);
  });

  it("handles an empty family", () => {
    expect(cycleVariant(0, 0)).toBe(0);
  });
});

describe("coherenceBadge", () => {
  it("passes a set whose tiles all abut cleanly", () => {
    expect(coherenceBadge(1)).toEqual({ percent: 100, ok: true, label: "tiles abut cleanly" });
  });

  it("flags a set with mismatched edges", () => {
    const badge = coherenceBadge(0.7);
    expect(badge.ok).toBe(false);
    expect(badge.label).toBe("edges mismatch");
    expect(badge.percent).toBe(70);
  });
});
