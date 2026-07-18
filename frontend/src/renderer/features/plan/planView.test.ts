import { describe, expect, it } from "vitest";

import type { SceneGraph } from "../../api/types";
import { planCaption, planSummary, silhouetteGrid } from "./planView";

function graph(overrides: Partial<SceneGraph> = {}): SceneGraph {
  return {
    schema_version: 2,
    id: "abc",
    entity: {
      kind: "character",
      subject: "a knight",
      intent: "heroic",
      parts: [
        { name: "helmet", description: "", z_order: 0, material: "steel", palette_index_refs: [] },
        { name: "cape", description: "", z_order: 1, material: null, palette_index_refs: [] },
      ],
      materials: [
        { name: "steel", kind: "metal", description: "", specular: true, dither_ok: true, ramp_size: 4 },
      ],
    },
    palette: { palette_id: "8bit-console", max_colors: 16, locked: true },
    lighting: { direction: "top-left", intensity: 0.6, single_source: true, rim_light: true },
    composition: {
      framing: "centered",
      margin_fraction: 0.1,
      focal_point: "center",
      balance: "symmetric",
    },
    silhouette: { grid: ["## ", " ##"], notes: "" },
    provenance: {
      user_prompt: "a knight",
      expanded_prompt: "a knight, ...",
      negative_prompt: "",
      seed: 42,
      mode: "character",
      style: "modern-indie",
      planning_backend: "mock",
      agent_trace: ["intent", "art-director", "composition"],
      model_versions: {},
    },
    tags: [],
    ...overrides,
  };
}

describe("planSummary", () => {
  it("summarizes subject, parts, materials, composition, lighting and palette", () => {
    const rows = planSummary(graph());
    const byLabel = Object.fromEntries(rows.map((r) => [r.label, r.value]));
    expect(byLabel.Subject).toBe("a knight");
    expect(byLabel.Parts).toBe("helmet, cape");
    expect(byLabel.Materials).toBe("steel (specular)");
    expect(byLabel.Lighting).toContain("top-left");
    expect(byLabel.Lighting).toContain("rim light");
    expect(byLabel.Palette).toContain("8bit-console");
    expect(byLabel.Palette).toContain("locked");
  });

  it("omits optional rows when empty", () => {
    const g = graph();
    g.entity.parts = [];
    g.entity.materials = [];
    g.entity.intent = "";
    const labels = planSummary(g).map((r) => r.label);
    expect(labels).not.toContain("Parts");
    expect(labels).not.toContain("Materials");
    expect(labels).not.toContain("Intent");
  });
});

describe("silhouetteGrid", () => {
  it("renders spaces as middots and returns null when absent", () => {
    expect(silhouetteGrid(graph())).toEqual(["##·", "·##"]);
    expect(silhouetteGrid(graph({ silhouette: null }))).toBeNull();
  });
});

describe("planCaption", () => {
  it("counts agents and names the backend", () => {
    expect(planCaption(graph())).toBe("planned by 3 agents · backend mock");
  });
});
