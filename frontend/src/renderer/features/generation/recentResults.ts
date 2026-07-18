/** Pure helper: flatten the generation job queue into a list of recent result images.
 *
 * Shared by the QA and Characters panels (both let you pick a recent sprite), and unit-tested so
 * the ordering/limit logic is verified without a store.
 */
import type { Job } from "../../api/types";

export interface RecentResult {
  filename: string;
  prompt: string;
}

/** Newest-first result images across all completed jobs, capped at ``limit``. */
export function recentResults(
  jobs: Record<string, Job>,
  jobOrder: string[],
  limit = 30,
): RecentResult[] {
  const items: RecentResult[] = [];
  for (const id of jobOrder) {
    const job = jobs[id];
    for (const image of job?.result?.images ?? []) {
      items.push({ filename: image.filename, prompt: job.request.prompt });
    }
  }
  return items.slice(0, limit);
}
