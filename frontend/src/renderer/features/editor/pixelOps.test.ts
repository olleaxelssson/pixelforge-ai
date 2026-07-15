import { describe, expect, it } from "vitest";

import {
  createBuffer,
  drawEllipse,
  drawLine,
  drawRect,
  floodFill,
  getPixel,
  hexToRgba,
  mergeLayers,
  setPixel,
  shiftBuffer,
} from "./pixelOps";

const RED: [number, number, number, number] = [255, 0, 0, 255];

describe("pixelOps", () => {
  it("sets and gets pixels", () => {
    const buffer = createBuffer(4, 4);
    setPixel(buffer, 4, 4, 1, 2, RED);
    expect(getPixel(buffer, 4, 1, 2)).toEqual(RED);
  });

  it("ignores out-of-bounds writes", () => {
    const buffer = createBuffer(4, 4);
    setPixel(buffer, 4, 4, -1, 0, RED);
    setPixel(buffer, 4, 4, 4, 0, RED);
    expect(buffer.every((v) => v === 0)).toBe(true);
  });

  it("draws diagonal lines endpoint to endpoint", () => {
    const out = drawLine(createBuffer(8, 8), 8, 8, 0, 0, 7, 7, RED);
    expect(getPixel(out, 8, 0, 0)).toEqual(RED);
    expect(getPixel(out, 8, 7, 7)).toEqual(RED);
    expect(getPixel(out, 8, 3, 3)).toEqual(RED);
  });

  it("draws rect outlines without filling", () => {
    const out = drawRect(createBuffer(8, 8), 8, 8, 1, 1, 5, 5, RED, false);
    expect(getPixel(out, 8, 1, 1)).toEqual(RED);
    expect(getPixel(out, 8, 3, 1)).toEqual(RED);
    expect(getPixel(out, 8, 3, 3)[3]).toBe(0);
  });

  it("draws filled ellipses containing center", () => {
    const out = drawEllipse(createBuffer(9, 9), 9, 9, 1, 1, 7, 7, RED, true);
    expect(getPixel(out, 9, 4, 4)).toEqual(RED);
  });

  it("flood fills a bounded region", () => {
    let buffer = drawRect(createBuffer(8, 8), 8, 8, 0, 0, 7, 7, RED, false);
    buffer = floodFill(buffer, 8, 8, 4, 4, [0, 255, 0, 255]);
    expect(getPixel(buffer, 8, 4, 4)).toEqual([0, 255, 0, 255]);
    expect(getPixel(buffer, 8, 0, 0)).toEqual(RED); // border untouched
  });

  it("flood fill is a no-op on same color", () => {
    const buffer = createBuffer(4, 4);
    const out = floodFill(buffer, 4, 4, 0, 0, [0, 0, 0, 0]);
    expect(out).toEqual(buffer);
  });

  it("shifts content and clears vacated pixels", () => {
    const buffer = createBuffer(4, 4);
    setPixel(buffer, 4, 4, 0, 0, RED);
    const out = shiftBuffer(buffer, 4, 4, 1, 1);
    expect(getPixel(out, 4, 1, 1)).toEqual(RED);
    expect(getPixel(out, 4, 0, 0)[3]).toBe(0);
  });

  it("merges layers with top layer priority", () => {
    const bottom = createBuffer(2, 2);
    setPixel(bottom, 2, 2, 0, 0, RED);
    const top = createBuffer(2, 2);
    setPixel(top, 2, 2, 0, 0, [0, 0, 255, 255]);
    const merged = mergeLayers([bottom, top], 2, 2);
    expect(getPixel(merged, 2, 0, 0)).toEqual([0, 0, 255, 255]);
  });

  it("parses hex colors", () => {
    expect(hexToRgba("#ff8800")).toEqual([255, 136, 0, 255]);
  });
});
