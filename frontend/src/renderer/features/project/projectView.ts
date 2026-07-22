/** Pure helpers for the Project menu (M25) — unit-tested; the React bar is not. */
import type { ProjectManifest } from "../../api/types";

/** The workspace is dirty when the current sprite count differs from what was last saved. */
export function isDirty(resultCount: number, savedCount: number | null): boolean {
  if (savedCount === null) return resultCount > 0; // never saved: dirty once anything exists
  return resultCount !== savedCount;
}

/** A filesystem-safe project name (matches the backend's own sanitisation). */
export function sanitizeName(name: string): string {
  return name.trim().replace(/\//g, "_") || "project";
}

export interface SummaryRow {
  label: string;
  value: string | number;
}

/** Headline rows for a just-opened project's manifest. */
export function projectSummary(manifest: ProjectManifest): SummaryRow[] {
  return [
    { label: "name", value: manifest.name },
    { label: "sprites", value: manifest.sprites.length },
    { label: "palettes", value: manifest.palettes.length },
    { label: "characters", value: manifest.characters.length },
    { label: "schema", value: `v${manifest.schema_version}` },
  ];
}
