/** Pure view helpers for the Pixel QA panel (D-013). */
import type { Finding, FindingSeverity, QAScores } from "../../api/types";

const SEVERITY_RANK: Record<FindingSeverity, number> = { error: 0, warning: 1, info: 2 };

/** Most-severe findings first; stable within a severity. */
export function orderedFindings(findings: Finding[]): Finding[] {
  return [...findings].sort((a, b) => SEVERITY_RANK[a.severity] - SEVERITY_RANK[b.severity]);
}

/** A 0..1 score as an integer percentage. */
export function scorePercent(value: number): number {
  return Math.round(Math.max(0, Math.min(1, value)) * 100);
}

export interface ScoreBar {
  label: string;
  percent: number;
}

/** The named sub-scores (excluding ``overall``, shown separately) as labeled bars. */
export function scoreBars(scores: QAScores): ScoreBar[] {
  return [
    { label: "Readability", percent: scorePercent(scores.readability) },
    { label: "Palette", percent: scorePercent(scores.palette) },
    { label: "Contrast", percent: scorePercent(scores.contrast) },
    { label: "Silhouette", percent: scorePercent(scores.silhouette) },
    { label: "Cleanliness", percent: scorePercent(scores.cleanliness) },
  ];
}

/** How many findings are repairable-worthy vs advisory, for a short caption. */
export function findingCounts(findings: Finding[]): { errors: number; warnings: number; infos: number } {
  return {
    errors: findings.filter((f) => f.severity === "error").length,
    warnings: findings.filter((f) => f.severity === "warning").length,
    infos: findings.filter((f) => f.severity === "info").length,
  };
}
