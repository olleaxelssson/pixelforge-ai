/** Pure view helpers for the Scene Graph plan preview (D-009/D-010).
 *
 * Kept separate from the React component so the summarization logic is unit-tested without a DOM.
 */
import type { SceneGraph } from "../../api/types";

export interface PlanRow {
  label: string;
  value: string;
}

/** Flatten the parts of a Scene Graph a pixel artist cares about into labeled rows. */
export function planSummary(graph: SceneGraph): PlanRow[] {
  const rows: PlanRow[] = [
    { label: "Subject", value: graph.entity.subject },
    { label: "Kind", value: graph.entity.kind },
  ];
  if (graph.entity.intent) rows.push({ label: "Intent", value: graph.entity.intent });

  const parts = graph.entity.parts.map((p) => p.name).filter(Boolean);
  if (parts.length) rows.push({ label: "Parts", value: parts.join(", ") });

  const materials = graph.entity.materials
    .map((m) => (m.specular ? `${m.name} (specular)` : m.name))
    .filter(Boolean);
  if (materials.length) rows.push({ label: "Materials", value: materials.join(", ") });

  rows.push({
    label: "Composition",
    value: `${graph.composition.framing}, ${graph.composition.balance}, focus ${graph.composition.focal_point}`,
  });

  const light = graph.lighting;
  rows.push({
    label: "Lighting",
    value: `${light.direction} · intensity ${light.intensity.toFixed(2)}${
      light.rim_light ? " · rim light" : ""
    }`,
  });

  rows.push({
    label: "Palette",
    value: `${graph.palette.palette_id ?? "auto"} · ≤${graph.palette.max_colors} colors${
      graph.palette.locked ? " · locked" : ""
    }`,
  });

  return rows;
}

/** Render the silhouette occupancy grid as text rows (``#`` filled, ``·`` empty), or null. */
export function silhouetteGrid(graph: SceneGraph): string[] | null {
  const grid = graph.silhouette?.grid;
  if (!grid || grid.length === 0) return null;
  return grid.map((line) => line.replace(/ /g, "·"));
}

/** A one-line provenance caption: backend + agent count. */
export function planCaption(graph: SceneGraph): string {
  const backend = graph.provenance.planning_backend || "mock";
  const agents = graph.provenance.agent_trace.length;
  return `planned by ${agents} agent${agents === 1 ? "" : "s"} · backend ${backend}`;
}
