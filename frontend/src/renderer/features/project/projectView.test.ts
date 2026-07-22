import { describe, expect, it } from "vitest";

import type { ProjectManifest } from "../../api/types";
import { isDirty, projectSummary, sanitizeName } from "./projectView";

describe("isDirty", () => {
  it("is clean before anything is generated and never saved", () => {
    expect(isDirty(0, null)).toBe(false);
  });

  it("is dirty once results exist and nothing was saved", () => {
    expect(isDirty(3, null)).toBe(true);
  });

  it("is clean right after saving the current count", () => {
    expect(isDirty(3, 3)).toBe(false);
  });

  it("is dirty when new results arrive after a save", () => {
    expect(isDirty(5, 3)).toBe(true);
  });
});

describe("sanitizeName", () => {
  it("keeps a clean name and falls back when empty", () => {
    expect(sanitizeName("My Game")).toBe("My Game");
    expect(sanitizeName("  ")).toBe("project");
    expect(sanitizeName("a/b")).toBe("a_b");
  });
});

describe("projectSummary", () => {
  it("surfaces the manifest headline counts", () => {
    const manifest: ProjectManifest = {
      schema_version: 1,
      app_version: "0.1.0",
      name: "Demo",
      created_at: 100,
      sprites: ["a.png", "b.png"],
      palettes: [{ id: "p" }],
      characters: [],
      project: {},
      metadata: {},
    };
    expect(projectSummary(manifest)).toEqual([
      { label: "name", value: "Demo" },
      { label: "sprites", value: 2 },
      { label: "palettes", value: 1 },
      { label: "characters", value: 0 },
      { label: "schema", value: "v1" },
    ]);
  });
});
