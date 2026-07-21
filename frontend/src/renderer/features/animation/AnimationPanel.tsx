import { useEffect, useRef, useState } from "react";

import { api } from "../../api/client";
import type { AnimationAction, AnimationResult } from "../../api/types";
import { useGenerationStore } from "../../state/generationStore";
import { nextFrame, onionFrame } from "./playback";

const SIZES = [16, 24, 32, 48, 64];

export function AnimationPanel() {
  const palettes = useGenerationStore((state) => state.palettes);
  const backendOnline = useGenerationStore((state) => state.backendOnline);

  const [actions, setActions] = useState<AnimationAction[]>([]);
  const [prompt, setPrompt] = useState("");
  const [action, setAction] = useState("walk");
  const [size, setSize] = useState(32);
  const [seed, setSeed] = useState<string>("7");
  const [paletteId, setPaletteId] = useState("");
  const [frameMs, setFrameMs] = useState(120);

  const [result, setResult] = useState<AnimationResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [frame, setFrame] = useState(0);
  const [playing, setPlaying] = useState(true);
  const [onion, setOnion] = useState(false);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    api.animationActions().then(setActions).catch(() => setActions([]));
  }, []);

  // Playback loop: advance frames while playing.
  useEffect(() => {
    if (timer.current) clearInterval(timer.current);
    if (!result || !playing) return;
    timer.current = setInterval(() => {
      setFrame((f) => nextFrame(f, result.frames.length, result.loop));
    }, result.frame_duration_ms);
    return () => {
      if (timer.current) clearInterval(timer.current);
    };
  }, [result, playing]);

  const generate = async () => {
    if (!prompt.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const animation = await api.animate({
        prompt,
        action,
        width: size,
        height: size,
        seed: seed === "" ? null : Number(seed),
        palette_id: paletteId || null,
        frame_duration_ms: frameMs,
      });
      setResult(animation);
      setFrame(0);
      setPlaying(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "animation failed");
      setResult(null);
    } finally {
      setBusy(false);
    }
  };

  const ghost = result ? onionFrame(frame, result.frames.length, result.loop) : null;
  const current = result?.frames[frame];

  return (
    <div className="studio-panel">
      <aside className="panel">
        <h2>Animate</h2>

        <div className="field">
          <label>Prompt</label>
          <textarea
            value={prompt}
            placeholder="a knight with a flaming sword"
            onChange={(e) => setPrompt(e.target.value)}
          />
        </div>

        <div className="field">
          <label>Action</label>
          <select value={action} onChange={(e) => setAction(e.target.value)}>
            {actions.map((a) => (
              <option key={a.id} value={a.id}>
                {a.name} ({a.frame_count}f{a.loop ? ", loop" : ""})
              </option>
            ))}
          </select>
        </div>

        <div className="field-row">
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
          <label>Palette (blank = lock frame 1&rsquo;s)</label>
          <select value={paletteId} onChange={(e) => setPaletteId(e.target.value)}>
            <option value="">Auto (locked across frames)</option>
            {palettes.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </div>

        <div className="field">
          <label>Frame duration: {frameMs} ms</label>
          <input
            type="range"
            min={40}
            max={400}
            step={10}
            value={frameMs}
            onChange={(e) => setFrameMs(Number(e.target.value))}
          />
        </div>

        <button
          className="primary-button"
          disabled={!backendOnline || !prompt.trim() || busy}
          onClick={() => void generate()}
        >
          {busy ? "Generating…" : "Generate animation"}
        </button>
        {error && <div className="error-text">{error}</div>}
      </aside>

      <section className="results">
        {!result && (
          <p style={{ color: "var(--text-dim)" }}>
            Generate a seed-anchored, palette-locked frame sequence — assembled into a looping GIF and
            a sprite sheet, with an onion-skin preview.
          </p>
        )}

        {result && current && (
          <div className="anim-view">
            <div className="anim-stage-wrap">
              <div className="anim-stage">
                {onion && ghost !== null && (
                  <img
                    className="anim-frame ghost"
                    src={api.imageUrl(result.frames[ghost].filename)}
                    alt="onion skin"
                  />
                )}
                <img
                  className="anim-frame"
                  src={api.imageUrl(current.filename)}
                  alt={current.description}
                />
              </div>
              <div className="anim-controls">
                <button className="small-button" onClick={() => setPlaying((p) => !p)}>
                  {playing ? "⏸ Pause" : "▶ Play"}
                </button>
                <label className="anim-toggle">
                  <input
                    type="checkbox"
                    checked={onion}
                    onChange={(e) => setOnion(e.target.checked)}
                  />{" "}
                  Onion skin
                </label>
                <span className="anim-caption">
                  {result.action_name} · frame {frame + 1}/{result.frames.length}
                </span>
              </div>
              <p className="anim-desc">{current.description}</p>
            </div>

            <div className="anim-side">
              <div className="anim-block">
                <h4>Timeline</h4>
                <div className="filmstrip">
                  {result.frames.map((f, i) => (
                    <button
                      key={f.filename}
                      className={`filmstrip-frame ${i === frame ? "active" : ""}`}
                      onClick={() => {
                        setPlaying(false);
                        setFrame(i);
                      }}
                      title={f.description}
                    >
                      <img src={api.imageUrl(f.filename)} alt={`frame ${i + 1}`} />
                    </button>
                  ))}
                </div>
              </div>

              <div className="anim-block">
                <h4>Locked palette ({result.palette_hex.length})</h4>
                <div className="swatch-row">
                  {result.palette_hex.map((hex, i) => (
                    <span
                      key={`${hex}-${i}`}
                      className="swatch"
                      style={{ background: hex, width: 20, height: 20 }}
                      title={hex}
                    />
                  ))}
                </div>
              </div>

              <div className="anim-block">
                <h4>Export</h4>
                <div className="anim-export">
                  <a href={api.imageUrl(result.gif_filename)} download>
                    <img className="anim-gif" src={api.imageUrl(result.gif_filename)} alt="GIF" />
                  </a>
                  <div className="anim-links">
                    <a className="link-button" href={api.imageUrl(result.gif_filename)} download>
                      download GIF
                    </a>
                    <a className="link-button" href={api.imageUrl(result.sheet_filename)} download>
                      download sprite sheet
                    </a>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
