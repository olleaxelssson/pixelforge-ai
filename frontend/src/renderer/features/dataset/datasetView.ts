/** Pure view helpers for the Dataset tab (M21) — unit-tested; the React panel is not. */
import type { DatasetItem, DatasetReport } from "../../api/types";

export type ItemStatus = "trainable" | "duplicate" | "invalid";

/** Classify an item for display: invalid (rejected), duplicate (near-dup), or trainable. */
export function itemStatus(item: DatasetItem): ItemStatus {
  if (!item.valid) return "invalid";
  if (item.duplicate_of !== null) return "duplicate";
  return "trainable";
}

export interface SummaryStat {
  label: string;
  value: number;
}

/** Headline counts for the summary strip. */
export function summaryStats(report: DatasetReport): SummaryStat[] {
  return [
    { label: "images", value: report.total },
    { label: "valid", value: report.valid_count },
    { label: "invalid", value: report.invalid_count },
    { label: "duplicates", value: report.duplicate_count },
    { label: "trainable", value: report.lora_config.image_count },
  ];
}

/** Render the manifest exactly as the emitted ``manifest.jsonl`` — one JSON record per line. */
export function manifestJsonl(report: DatasetReport): string {
  return report.manifest.map((record) => JSON.stringify(record)).join("\n");
}

/** Pretty-print the LoRA config as the emitted ``lora_config.json`` would look. */
export function configJson(report: DatasetReport): string {
  return JSON.stringify(report.lora_config, null, 2);
}
