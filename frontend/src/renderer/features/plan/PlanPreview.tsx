import { useState } from "react";

import { api } from "../../api/client";
import type { SceneGraph } from "../../api/types";
import { useGenerationStore } from "../../state/generationStore";
import { planCaption, planSummary, silhouetteGrid } from "./planView";

/** Inline "what would the agents decide?" preview for the current request (POST /api/plan). */
export function PlanPreview() {
  const request = useGenerationStore((state) => state.request);
  const backendOnline = useGenerationStore((state) => state.backendOnline);
  const [graph, setGraph] = useState<SceneGraph | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const preview = async () => {
    setLoading(true);
    setError(null);
    try {
      setGraph(await api.plan(request));
    } catch (e) {
      setError(e instanceof Error ? e.message : "plan failed");
      setGraph(null);
    } finally {
      setLoading(false);
    }
  };

  const grid = graph ? silhouetteGrid(graph) : null;

  return (
    <div className="plan-preview">
      <button
        className="secondary-button"
        disabled={!backendOnline || !request.prompt?.trim() || loading}
        onClick={() => void preview()}
      >
        {loading ? "Planning…" : "Preview plan"}
      </button>

      {error && <div className="error-text">{error}</div>}

      {graph && (
        <div className="plan-result">
          <div className="plan-caption">{planCaption(graph)}</div>

          <table className="plan-table">
            <tbody>
              {planSummary(graph).map((row) => (
                <tr key={row.label}>
                  <th>{row.label}</th>
                  <td>{row.value}</td>
                </tr>
              ))}
            </tbody>
          </table>

          {grid && (
            <div className="plan-section">
              <span className="plan-section-label">Silhouette</span>
              <pre className="silhouette-grid">{grid.join("\n")}</pre>
            </div>
          )}

          <div className="plan-section">
            <span className="plan-section-label">Compiled prompt</span>
            <p className="plan-prompt">{graph.provenance.expanded_prompt}</p>
          </div>

          {graph.provenance.agent_trace.length > 0 && (
            <div className="plan-section">
              <span className="plan-section-label">Agent trace</span>
              <div className="agent-trace">
                {graph.provenance.agent_trace.map((agent, i) => (
                  <span key={`${agent}-${i}`} className="agent-chip">
                    {agent}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
