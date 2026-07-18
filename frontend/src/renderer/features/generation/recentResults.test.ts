import { describe, expect, it } from "vitest";

import type { Job } from "../../api/types";
import { recentResults } from "./recentResults";

function job(id: string, prompt: string, filenames: string[]): Job {
  return {
    id,
    status: "completed",
    request: { prompt },
    progress: { stage: "done", percent: 100 },
    result: {
      images: filenames.map((filename) => ({
        filename,
        width: 32,
        height: 32,
        seed: 1,
        palette_hex: [],
      })),
    },
    error: null,
  };
}

describe("recentResults", () => {
  it("flattens images in jobOrder, newest first", () => {
    const jobs = {
      a: job("a", "knight", ["a0.png", "a1.png"]),
      b: job("b", "slime", ["b0.png"]),
    };
    const result = recentResults(jobs, ["b", "a"]);
    expect(result.map((r) => r.filename)).toEqual(["b0.png", "a0.png", "a1.png"]);
    expect(result[1].prompt).toBe("knight");
  });

  it("skips running/failed jobs with no result and respects the limit", () => {
    const jobs: Record<string, Job> = {
      a: job("a", "knight", ["a0.png", "a1.png", "a2.png"]),
      b: { ...job("b", "pending", []), status: "running", result: null },
    };
    expect(recentResults(jobs, ["a", "b"], 2).map((r) => r.filename)).toEqual(["a0.png", "a1.png"]);
  });

  it("returns an empty list when there are no jobs", () => {
    expect(recentResults({}, [])).toEqual([]);
  });
});
