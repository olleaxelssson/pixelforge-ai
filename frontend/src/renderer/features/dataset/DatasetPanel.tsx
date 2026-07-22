import { useState } from "react";

import { api } from "../../api/client";
import { fileToBase64 } from "../../api/image";
import type { DatasetReport } from "../../api/types";
import { useGenerationStore } from "../../state/generationStore";
import { configJson, itemStatus, manifestJsonl, summaryStats } from "./datasetView";

export function DatasetPanel() {
  const backendOnline = useGenerationStore((state) => state.backendOnline);

  const [dupDistance, setDupDistance] = useState(6);
  const [report, setReport] = useState<DatasetReport | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fileCount, setFileCount] = useState(0);

  const analyze = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    setBusy(true);
    setError(null);
    setFileCount(files.length);
    try {
      const images = await Promise.all(
        Array.from(files).map(async (file) => ({
          name: file.name,
          image_base64: await fileToBase64(file),
        })),
      );
      setReport(await api.analyzeDataset({ images, dup_distance: dupDistance }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "dataset analysis failed");
      setReport(null);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="studio-panel">
      <aside className="panel">
        <h2>Dataset</h2>
        <p style={{ color: "var(--text-dim)" }}>
          Import a folder of sprites to build a LoRA training set: validation, perceptual-hash dedup,
          auto-captioning, and a kohya-style manifest + config.
        </p>

        <div className="field">
          <label>Duplicate distance: {dupDistance} / 64 bits</label>
          <input
            type="range"
            min={0}
            max={16}
            step={1}
            value={dupDistance}
            onChange={(e) => setDupDistance(Number(e.target.value))}
          />
        </div>

        <div className="field">
          <label className="primary-button" style={{ textAlign: "center", cursor: "pointer" }}>
            {busy ? "Analyzing…" : "Choose sprites…"}
            <input
              type="file"
              accept="image/*"
              multiple
              disabled={!backendOnline || busy}
              style={{ display: "none" }}
              onChange={(e) => void analyze(e.target.files)}
            />
          </label>
          {fileCount > 0 && !busy && (
            <span style={{ color: "var(--text-dim)" }}>{fileCount} file(s) analyzed</span>
          )}
        </div>

        {error && <div className="error-text">{error}</div>}
        {!backendOnline && <div className="error-text">backend offline</div>}
      </aside>

      <section className="results">
        {!report && (
          <p style={{ color: "var(--text-dim)" }}>
            Select multiple sprite files. Corrupt or undersized images are flagged, near-duplicates
            are clustered out, and the remaining images become the training manifest.
          </p>
        )}

        {report && (
          <div className="dataset-view">
            <div className="dataset-summary">
              {summaryStats(report).map((stat) => (
                <div key={stat.label} className="dataset-stat">
                  <span className="dataset-stat-value">{stat.value}</span>
                  <span className="dataset-stat-label">{stat.label}</span>
                </div>
              ))}
            </div>

            <div className="dataset-block">
              <h4>Images</h4>
              <table className="dataset-table">
                <thead>
                  <tr>
                    <th>file</th>
                    <th>status</th>
                    <th>size</th>
                    <th>caption / issue</th>
                  </tr>
                </thead>
                <tbody>
                  {report.items.map((item) => {
                    const status = itemStatus(item);
                    return (
                      <tr key={item.name} className={`dataset-row ${status}`}>
                        <td>{item.name}</td>
                        <td>
                          <span className={`dataset-badge ${status}`}>{status}</span>
                        </td>
                        <td>{item.valid ? `${item.width}×${item.height}` : "—"}</td>
                        <td>
                          {status === "invalid"
                            ? item.issues.join("; ")
                            : status === "duplicate"
                              ? `≈ ${item.duplicate_of}`
                              : item.caption}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {report.clusters.length > 0 && (
              <div className="dataset-block">
                <h4>Duplicate clusters ({report.clusters.length})</h4>
                <ul className="dataset-clusters">
                  {report.clusters.map((cluster) => (
                    <li key={cluster.representative}>
                      <strong>{cluster.representative}</strong> ← {cluster.members.join(", ")}{" "}
                      <span style={{ color: "var(--text-dim)" }}>
                        (max {cluster.distance} bits)
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <div className="dataset-block">
              <h4>manifest.jsonl ({report.manifest.length} records)</h4>
              <pre className="dataset-code">{manifestJsonl(report) || "(empty)"}</pre>
            </div>

            <div className="dataset-block">
              <h4>lora_config.json</h4>
              <pre className="dataset-code">{configJson(report)}</pre>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
