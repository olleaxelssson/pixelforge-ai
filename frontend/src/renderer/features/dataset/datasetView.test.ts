import { describe, expect, it } from "vitest";

import type { DatasetItem, DatasetReport, LoraConfig } from "../../api/types";
import { configJson, itemStatus, manifestJsonl, summaryStats } from "./datasetView";

function item(overrides: Partial<DatasetItem>): DatasetItem {
  return {
    name: "x.png",
    valid: true,
    width: 32,
    height: 32,
    issues: [],
    phash: "0".repeat(16),
    caption: "",
    tags: [],
    duplicate_of: null,
    ...overrides,
  };
}

const loraConfig: LoraConfig = {
  base_model: "black-forest-labs/FLUX.1-schnell",
  resolution: 512,
  network_dim: 16,
  network_alpha: 8,
  learning_rate: 1e-4,
  train_batch_size: 2,
  max_train_epochs: 10,
  optimizer: "AdamW8bit",
  lr_scheduler: "cosine",
  mixed_precision: "bf16",
  trigger_word: "pixelforge_style",
  image_count: 2,
};

const report: DatasetReport = {
  root: "uploaded",
  total: 4,
  valid_count: 3,
  invalid_count: 1,
  duplicate_count: 1,
  items: [
    item({ name: "a.png" }),
    item({ name: "b.png", duplicate_of: "a.png" }),
    item({ name: "c.png" }),
    item({ name: "bad.png", valid: false, issues: ["corrupt"] }),
  ],
  clusters: [{ representative: "a.png", members: ["b.png"], distance: 2 }],
  lora_config: loraConfig,
  manifest: [
    { file_name: "a.png", caption: "sprite", tags: ["pixel-art"], width: 32, height: 32 },
    { file_name: "c.png", caption: "sprite", tags: ["pixel-art"], width: 32, height: 32 },
  ],
  manifest_path: null,
  config_path: null,
};

describe("itemStatus", () => {
  it("classifies invalid, duplicate, and trainable items", () => {
    expect(itemStatus(item({ valid: false }))).toBe("invalid");
    expect(itemStatus(item({ duplicate_of: "a.png" }))).toBe("duplicate");
    expect(itemStatus(item({}))).toBe("trainable");
  });
});

describe("summaryStats", () => {
  it("surfaces the headline counts", () => {
    expect(summaryStats(report)).toEqual([
      { label: "images", value: 4 },
      { label: "valid", value: 3 },
      { label: "invalid", value: 1 },
      { label: "duplicates", value: 1 },
      { label: "trainable", value: 2 },
    ]);
  });
});

describe("manifestJsonl", () => {
  it("renders one JSON record per line", () => {
    const lines = manifestJsonl(report).split("\n");
    expect(lines).toHaveLength(2);
    expect(JSON.parse(lines[0]).file_name).toBe("a.png");
    expect(JSON.parse(lines[1]).file_name).toBe("c.png");
  });
});

describe("configJson", () => {
  it("pretty-prints the LoRA config", () => {
    const json = configJson(report);
    expect(JSON.parse(json).image_count).toBe(2);
    expect(json).toContain("\n  ");
  });
});
