import { describe, expect, it } from "vitest";

import type { Finding, QAScores } from "../../api/types";
import { findingCounts, orderedFindings, scoreBars, scorePercent } from "./qaView";

function finding(severity: Finding["severity"], detector: string): Finding {
  return { detector, severity, message: `${detector} msg`, region: null };
}

describe("orderedFindings", () => {
  it("sorts errors before warnings before infos", () => {
    const findings = [
      finding("info", "light"),
      finding("error", "floating"),
      finding("warning", "palette"),
    ];
    expect(orderedFindings(findings).map((f) => f.severity)).toEqual(["error", "warning", "info"]);
  });

  it("does not mutate the input array", () => {
    const findings = [finding("info", "a"), finding("error", "b")];
    orderedFindings(findings);
    expect(findings[0].severity).toBe("info");
  });
});

describe("scorePercent", () => {
  it("clamps and rounds to a percentage", () => {
    expect(scorePercent(0.5)).toBe(50);
    expect(scorePercent(1.4)).toBe(100);
    expect(scorePercent(-0.2)).toBe(0);
    expect(scorePercent(0.126)).toBe(13);
  });
});

describe("scoreBars", () => {
  it("produces five labeled bars excluding overall", () => {
    const scores: QAScores = {
      readability: 0.8,
      palette: 0.9,
      contrast: 0.7,
      silhouette: 0.6,
      cleanliness: 1,
      overall: 0.8,
    };
    const bars = scoreBars(scores);
    expect(bars.map((b) => b.label)).toEqual([
      "Readability",
      "Palette",
      "Contrast",
      "Silhouette",
      "Cleanliness",
    ]);
    expect(bars[0].percent).toBe(80);
  });
});

describe("findingCounts", () => {
  it("tallies by severity", () => {
    const findings = [
      finding("error", "a"),
      finding("warning", "b"),
      finding("warning", "c"),
      finding("info", "d"),
    ];
    expect(findingCounts(findings)).toEqual({ errors: 1, warnings: 2, infos: 1 });
  });
});
