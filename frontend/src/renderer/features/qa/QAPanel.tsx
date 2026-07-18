import { useEffect, useMemo, useState } from "react";

import { api } from "../../api/client";
import { decodeImage, fileToBase64, imageUrlToBase64 } from "../../api/image";
import type { QAReport } from "../../api/types";
import { useCharactersStore } from "../../state/charactersStore";
import { useEditorStore } from "../../state/editorStore";
import { useGenerationStore } from "../../state/generationStore";
import { recentResults } from "../generation/recentResults";
import { findingCounts, orderedFindings, scoreBars, scorePercent } from "./qaView";

const LIGHTING = ["", "top-left", "top", "top-right", "left", "right", "bottom-left", "bottom"];

export function QAPanel() {
  const jobs = useGenerationStore((state) => state.jobs);
  const jobOrder = useGenerationStore((state) => state.jobOrder);
  const palettes = useGenerationStore((state) => state.palettes);
  const backendOnline = useGenerationStore((state) => state.backendOnline);
  const loadImageData = useEditorStore((state) => state.loadImageData);
  const characters = useCharactersStore((state) => state.characters);
  const loadCharacters = useCharactersStore((state) => state.load);

  useEffect(() => {
    void loadCharacters();
  }, [loadCharacters]);

  // A sprite the panel is working on, as a PNG data URL.
  const [source, setSource] = useState<string | null>(null);
  const [repaired, setRepaired] = useState<string | null>(null);
  const [report, setReport] = useState<QAReport | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [maxColors, setMaxColors] = useState(16);
  const [paletteId, setPaletteId] = useState<string>("");
  const [lighting, setLighting] = useState<string>("");

  const results = useMemo(() => recentResults(jobs, jobOrder), [jobs, jobOrder]);
  const characterFrames = useMemo(
    () =>
      characters.flatMap((c) =>
        c.reference_frames.map((f) => ({
          filename: f.filename,
          label: `${c.name} · ${f.label}`,
        })),
      ),
    [characters],
  );

  const reset = () => {
    setReport(null);
    setRepaired(null);
    setError(null);
  };

  const pickResult = async (filename: string) => {
    if (!filename) return;
    reset();
    try {
      setSource(await imageUrlToBase64(api.imageUrl(filename)));
    } catch (e) {
      setError(e instanceof Error ? e.message : "could not load result");
    }
  };

  const pickFile = async (file: File | undefined) => {
    if (!file) return;
    reset();
    setSource(await fileToBase64(file));
  };

  const run = async (repair: boolean) => {
    if (!source) return;
    setBusy(true);
    setError(null);
    try {
      const response = await api.qa({
        image_base64: source,
        max_colors: maxColors,
        palette_id: paletteId || null,
        lighting_direction: lighting || null,
        repair,
      });
      setReport(response.report);
      if (repair && response.repaired_image_base64) {
        setRepaired(`data:image/png;base64,${response.repaired_image_base64}`);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "QA failed");
    } finally {
      setBusy(false);
    }
  };

  const openRepairedInEditor = async () => {
    if (!repaired) return;
    const { data, width, height } = await decodeImage(repaired);
    loadImageData(data, width, height);
  };

  const counts = report ? findingCounts(report.findings) : null;

  return (
    <div className="studio-panel">
      <div className="panel qa-controls">
        <h2>Pixel QA</h2>

        <div className="field">
          <label>Sprite from a recent result</label>
          <select
            value=""
            disabled={results.length === 0}
            onChange={(e) => void pickResult(e.target.value)}
          >
            <option value="">{results.length ? "Choose a result…" : "No results yet"}</option>
            {results.map((r) => (
              <option key={r.filename} value={r.filename}>
                {r.prompt.slice(0, 32) || r.filename}
              </option>
            ))}
          </select>
        </div>

        <div className="field">
          <label>…or a character reference frame</label>
          <select
            value=""
            disabled={characterFrames.length === 0}
            onChange={(e) => void pickResult(e.target.value)}
          >
            <option value="">
              {characterFrames.length ? "Choose a frame…" : "No character frames yet"}
            </option>
            {characterFrames.map((f) => (
              <option key={f.filename} value={f.filename}>
                {f.label}
              </option>
            ))}
          </select>
        </div>

        <div className="field">
          <label>…or upload a PNG</label>
          <input
            type="file"
            accept="image/png,image/*"
            onChange={(e) => void pickFile(e.target.files?.[0])}
          />
        </div>

        <div className="field-row">
          <div className="field">
            <label>Max colors</label>
            <input
              type="number"
              min={2}
              max={256}
              value={maxColors}
              onChange={(e) => setMaxColors(Number(e.target.value))}
            />
          </div>
          <div className="field">
            <label>Palette</label>
            <select value={paletteId} onChange={(e) => setPaletteId(e.target.value)}>
              <option value="">Any</option>
              {palettes.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="field">
          <label>Expected light direction (enables the light-dir check)</label>
          <select value={lighting} onChange={(e) => setLighting(e.target.value)}>
            {LIGHTING.map((d) => (
              <option key={d || "none"} value={d}>
                {d || "Unset"}
              </option>
            ))}
          </select>
        </div>

        <div className="button-row">
          <button
            className="primary-button"
            disabled={!backendOnline || !source || busy}
            onClick={() => void run(false)}
          >
            {busy ? "Running…" : "Run QA"}
          </button>
          <button
            className="secondary-button"
            disabled={!backendOnline || !source || busy}
            onClick={() => void run(true)}
          >
            Apply safe repairs
          </button>
        </div>

        {error && <div className="error-text">{error}</div>}
      </div>

      <section className="results qa-results">
        {!source && (
          <p style={{ color: "var(--text-dim)" }}>
            Choose a sprite, then run the deterministic QA detectors (floating pixels, broken
            clusters, palette overflow, silhouette, pillow shading, light direction).
          </p>
        )}

        {source && (
          <div className="qa-images">
            <figure>
              <img className="qa-image" src={source} alt="original sprite" />
              <figcaption>original</figcaption>
            </figure>
            {repaired && (
              <figure>
                <img className="qa-image" src={repaired} alt="repaired sprite" />
                <figcaption>
                  repaired ·{" "}
                  <button className="link-button" onClick={() => void openRepairedInEditor()}>
                    open in editor
                  </button>
                </figcaption>
              </figure>
            )}
          </div>
        )}

        {report && (
          <>
            <div className={`qa-verdict ${report.passed ? "pass" : "fail"}`}>
              {report.passed ? "PASS" : "NEEDS WORK"} · overall {scorePercent(report.scores.overall)}%
              {counts && (
                <span className="qa-counts">
                  {counts.errors} error{counts.errors === 1 ? "" : "s"} · {counts.warnings} warning
                  {counts.warnings === 1 ? "" : "s"} · {counts.infos} advisory
                </span>
              )}
            </div>

            <div className="score-bars">
              {scoreBars(report.scores).map((bar) => (
                <div key={bar.label} className="score-bar">
                  <span className="score-label">{bar.label}</span>
                  <div className="score-track">
                    <div className="score-fill" style={{ width: `${bar.percent}%` }} />
                  </div>
                  <span className="score-value">{bar.percent}%</span>
                </div>
              ))}
            </div>

            {report.findings.length === 0 ? (
              <p style={{ color: "var(--success)" }}>No defects detected.</p>
            ) : (
              <ul className="finding-list">
                {orderedFindings(report.findings).map((f, i) => (
                  <li key={`${f.detector}-${i}`} className={`finding ${f.severity}`}>
                    <span className="finding-severity">{f.severity}</span>
                    <span className="finding-detector">{f.detector}</span>
                    <span className="finding-message">{f.message}</span>
                    {f.region && (
                      <span className="finding-region">
                        @ {f.region.x},{f.region.y} {f.region.width}×{f.region.height}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </>
        )}
      </section>
    </div>
  );
}
