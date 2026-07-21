import { describe, expect, it } from "vitest";

import { nextFrame, onionFrame } from "./playback";

describe("nextFrame", () => {
  it("advances through frames", () => {
    expect(nextFrame(0, 4, true)).toBe(1);
    expect(nextFrame(2, 4, true)).toBe(3);
  });

  it("wraps to 0 when looping", () => {
    expect(nextFrame(3, 4, true)).toBe(0);
  });

  it("clamps on the last frame when not looping", () => {
    expect(nextFrame(4, 5, false)).toBe(4);
    expect(nextFrame(3, 4, false)).toBe(3);
  });

  it("handles an empty sequence", () => {
    expect(nextFrame(0, 0, true)).toBe(0);
  });
});

describe("onionFrame", () => {
  it("returns the previous frame", () => {
    expect(onionFrame(2, 6, true)).toBe(1);
  });

  it("wraps to the last frame on frame 0 when looping", () => {
    expect(onionFrame(0, 6, true)).toBe(5);
  });

  it("returns null on frame 0 when not looping", () => {
    expect(onionFrame(0, 6, false)).toBeNull();
  });
});
