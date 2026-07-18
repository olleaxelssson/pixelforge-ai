import { useEffect, useMemo, useState } from "react";

import { api } from "../../api/client";
import type { PaletteAnalysis } from "../../api/types";
import { useGenerationStore } from "../../state/generationStore";

function Swatch({ hex, size = 20 }: { hex: string; size?: number }) {
  return (
    <span
      className="swatch"
      style={{ background: hex, width: size, height: size }}
      title={hex}
    />
  );
}

export function PalettePanel() {
  const palettes = useGenerationStore((state) => state.palettes);
  const backendOnline = useGenerationStore((state) => state.backendOnline);
  const [paletteId, setPaletteId] = useState<string>("");
  const [analysis, setAnalysis] = useState<PaletteAnalysis | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Default to the first palette once catalogs load.
  useEffect(() => {
    if (!paletteId && palettes.length) setPaletteId(palettes[0].id);
  }, [palettes, paletteId]);

  const selected = useMemo(() => palettes.find((p) => p.id === paletteId), [palettes, paletteId]);

  const analyze = async () => {
    if (!paletteId) return;
    setBusy(true);
    setError(null);
    try {
      setAnalysis(await api.paletteAnalysis(paletteId));
    } catch (e) {
      setError(e instanceof Error ? e.message : "analysis failed");
      setAnalysis(null);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="studio-panel">
      <aside className="panel">
        <h2>Palette lab</h2>
        <div className="field">
          <label>Palette</label>
          <select value={paletteId} onChange={(e) => setPaletteId(e.target.value)}>
            {palettes.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} ({p.colors.length})
              </option>
            ))}
          </select>
        </div>

        {selected && (
          <div className="swatch-row">
            {selected.colors.map((hex, i) => (
              <Swatch key={`${hex}-${i}`} hex={hex} />
            ))}
          </div>
        )}

        <button
          className="primary-button"
          disabled={!backendOnline || !paletteId || busy}
          onClick={() => void analyze()}
        >
          {busy ? "Analyzing…" : "Analyze"}
        </button>
        {error && <div className="error-text">{error}</div>}
      </aside>

      <section className="results">
        {!analysis && (
          <p style={{ color: "var(--text-dim)" }}>
            Analyze a palette for perceptual contrast (CIEDE2000 / WCAG), color-vision-deficiency
            confusions, shading ramps, and readability.
          </p>
        )}

        {analysis && (
          <div className="palette-analysis">
            <div className="analysis-headline">
              <span className="metric">
                <span className="metric-value">{Math.round(analysis.readability_score * 100)}%</span>
                <span className="metric-label">readability</span>
              </span>
              <span className="metric">
                <span className="metric-value">{analysis.color_count}</span>
                <span className="metric-label">colors</span>
              </span>
              <span className="metric">
                <span className="metric-value">
                  {analysis.contrast.max_contrast_ratio.toFixed(1)}:1
                </span>
                <span className="metric-label">max contrast</span>
              </span>
              <span className="metric">
                <span className="metric-value">{analysis.contrast.mean_delta_e.toFixed(1)}</span>
                <span className="metric-label">mean ΔE</span>
              </span>
            </div>

            {analysis.suggestions.length > 0 && (
              <div className="analysis-block">
                <h4>Suggestions</h4>
                <ul className="suggestion-list">
                  {analysis.suggestions.map((s, i) => (
                    <li key={`${s.code}-${i}`} className={`suggestion ${s.severity}`}>
                      <span className="suggestion-severity">{s.severity}</span>
                      {s.message}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {analysis.ramps.length > 0 && (
              <div className="analysis-block">
                <h4>Shading ramps</h4>
                {analysis.ramps.map((ramp, i) => (
                  <div key={i} className="swatch-row">
                    {ramp.map((hex, j) => (
                      <Swatch key={`${hex}-${j}`} hex={hex} size={24} />
                    ))}
                  </div>
                ))}
              </div>
            )}

            {analysis.duplicates.length > 0 && (
              <div className="analysis-block">
                <h4>Near-duplicates (ΔE &lt; 2)</h4>
                {analysis.duplicates.map((pair, i) => (
                  <div key={i} className="pair-row">
                    <Swatch hex={pair.a} />
                    <Swatch hex={pair.b} />
                    <span className="pair-meta">ΔE {pair.delta_e.toFixed(2)}</span>
                  </div>
                ))}
              </div>
            )}

            {analysis.cvd.length > 0 && (
              <div className="analysis-block">
                <h4>Color-vision-deficiency simulation</h4>
                {analysis.cvd.map((report) => (
                  <div key={report.vision} className="cvd-report">
                    <div className="cvd-head">
                      <span className="cvd-name">{report.vision}</span>
                      {report.confusable_pairs.length > 0 && (
                        <span className="cvd-warn">
                          {report.confusable_pairs.length} confusable pair
                          {report.confusable_pairs.length === 1 ? "" : "s"}
                        </span>
                      )}
                    </div>
                    <div className="swatch-row">
                      {report.simulated_hex.map((hex, j) => (
                        <Swatch key={`${hex}-${j}`} hex={hex} />
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </section>
    </div>
  );
}
