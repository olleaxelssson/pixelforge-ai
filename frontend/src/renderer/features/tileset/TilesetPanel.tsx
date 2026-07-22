import { useMemo, useState } from "react";

import { api, downloadExport } from "../../api/client";
import type { TileSetResult } from "../../api/types";
import { useGenerationStore } from "../../state/generationStore";
import { coherenceBadge, createGrid, paintCell } from "./tilesetView";

const SIZES = [16, 24, 32, 48, 64];
const GRID = 4; // paintable N×N preview
const CELL = 56; // displayed px per tile

export function TilesetPanel() {
  const palettes = useGenerationStore((state) => state.palettes);
  const backendOnline = useGenerationStore((state) => state.backendOnline);

  const [prompt, setPrompt] = useState("");
  const [variants, setVariants] = useState(4);
  const [size, setSize] = useState(32);
  const [seed, setSeed] = useState("5");
  const [paletteId, setPaletteId] = useState("");

  const [result, setResult] = useState<TileSetResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [grid, setGrid] = useState<number[]>(() => createGrid(GRID));
  const [active, setActive] = useState(0);

  const badge = useMemo(
    () => (result ? coherenceBadge(result.min_edge_consistency) : null),
    [result],
  );

  const generate = async () => {
    if (!prompt.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const set = await api.generateTileset({
        prompt,
        variants,
        width: size,
        height: size,
        seed: seed === "" ? null : Number(seed),
        palette_id: paletteId || null,
      });
      setResult(set);
      setActive(0);
      // Seed the paint grid with a deterministic sampling of the family.
      setGrid(createGrid(GRID).map((_, i) => i % set.variant_count));
    } catch (e) {
      setError(e instanceof Error ? e.message : "tileset generation failed");
      setResult(null);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="studio-panel">
      <aside className="panel">
        <h2>Tileset</h2>
        <p style={{ color: "var(--text-dim)" }}>
          Generate a coherent terrain family — a base tile plus seam-locked variants that share
          edges, so any two abut cleanly and each tiles by itself.
        </p>

        <div className="field">
          <label>Prompt</label>
          <textarea
            value={prompt}
            placeholder="grass field"
            onChange={(e) => setPrompt(e.target.value)}
          />
        </div>

        <div className="field-row">
          <div className="field">
            <label>Variants</label>
            <input
              type="number"
              min={1}
              max={16}
              value={variants}
              onChange={(e) => setVariants(Number(e.target.value))}
            />
          </div>
          <div className="field">
            <label>Size</label>
            <select value={size} onChange={(e) => setSize(Number(e.target.value))}>
              {SIZES.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label>Seed</label>
            <input value={seed} onChange={(e) => setSeed(e.target.value)} />
          </div>
        </div>

        <div className="field">
          <label>Palette (blank = lock the base tile&rsquo;s)</label>
          <select value={paletteId} onChange={(e) => setPaletteId(e.target.value)}>
            <option value="">Auto (locked across variants)</option>
            {palettes.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </div>

        <button
          className="primary-button"
          disabled={!backendOnline || !prompt.trim() || busy}
          onClick={() => void generate()}
        >
          {busy ? "Generating…" : "Generate tileset"}
        </button>
        {error && <div className="error-text">{error}</div>}
      </aside>

      <section className="results">
        {!result && (
          <p style={{ color: "var(--text-dim)" }}>
            Generate a set, then paint the grid: pick a variant and click cells to see the tiles
            abut seamlessly.
          </p>
        )}

        {result && (
          <div className="tileset-view">
            <div className="tileset-head">
              {badge && (
                <span className={`tileset-badge ${badge.ok ? "ok" : "warn"}`}>
                  {badge.percent}% · {badge.label}
                </span>
              )}
              <span style={{ color: "var(--text-dim)" }}>
                {result.variant_count} variants · seed {result.base_seed} · mean edge{" "}
                {Math.round(result.mean_edge_consistency * 100)}%
              </span>
            </div>

            <div className="tileset-block">
              <h4>Variants — click to select a brush</h4>
              <div className="tileset-variants">
                {result.tiles.map((tile) => (
                  <button
                    key={tile.filename}
                    className={`tileset-variant ${active === tile.index ? "active" : ""}`}
                    onClick={() => setActive(tile.index)}
                    title={`variant ${tile.index} · seed ${tile.seed} · abuts base ${Math.round(
                      tile.edge_consistency * 100,
                    )}%`}
                  >
                    <img src={api.imageUrl(tile.filename)} alt={`variant ${tile.index}`} />
                    <span>{tile.index}</span>
                  </button>
                ))}
              </div>
            </div>

            <div className="tileset-block">
              <h4>Paintable preview ({GRID}×{GRID}) — click a cell to paint</h4>
              <div
                className="tileset-grid"
                style={{ gridTemplateColumns: `repeat(${GRID}, ${CELL}px)` }}
              >
                {grid.map((variant, i) => (
                  <button
                    key={i}
                    className="tileset-cell"
                    style={{ width: CELL, height: CELL }}
                    onClick={() => setGrid((g) => paintCell(g, i, active))}
                    title={`cell ${i} · variant ${variant}`}
                  >
                    <img
                      src={api.imageUrl(result.tiles[variant]?.filename ?? result.tiles[0].filename)}
                      alt={`cell ${i}`}
                    />
                  </button>
                ))}
              </div>
              <p style={{ color: "var(--text-dim)", fontSize: 12 }}>
                Cells render edge-to-edge — because the variants share edges, the terrain reads as
                one continuous surface.
              </p>
            </div>

            <div className="tileset-block">
              <h4>Auto-tile sheet</h4>
              <a href={api.imageUrl(result.sheet_filename)} download>
                <img
                  className="tileset-sheet"
                  src={api.imageUrl(result.sheet_filename)}
                  alt="47-tile Wang/blob sheet"
                />
              </a>
              <div>
                <a className="link-button" href={api.imageUrl(result.sheet_filename)} download>
                  download 47-tile Wang/blob sheet
                </a>
              </div>
            </div>

            <div className="tileset-block">
              <h4>Export for a game engine</h4>
              <div className="tileset-export">
                <button
                  className="link-button"
                  onClick={() =>
                    void downloadExport({
                      format_id: "godot-tileset",
                      filenames: result.tiles.map((t) => t.filename),
                      options: { base_name: result.prompt.replace(/\W+/g, "_") || "tileset" },
                    })
                  }
                >
                  download Godot 4 TileSet (.tres)
                </button>
                <button
                  className="link-button"
                  onClick={() =>
                    void downloadExport({
                      format_id: "tiled-tileset",
                      filenames: result.tiles.map((t) => t.filename),
                      options: { base_name: result.prompt.replace(/\W+/g, "_") || "tileset" },
                    })
                  }
                >
                  download Tiled tileset (.tsx + .tmx)
                </button>
              </div>
              <p style={{ color: "var(--text-dim)", fontSize: 12 }}>
                Terrain peering bits / wangsets are baked from the 47-blob masks, so autotiling works
                on import.
              </p>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
