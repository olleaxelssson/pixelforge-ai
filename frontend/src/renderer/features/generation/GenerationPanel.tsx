import { useGenerationStore } from "../../state/generationStore";

const SIZES = [16, 24, 32, 48, 64, 96, 128, 256];

export function GenerationPanel() {
  const { modes, styles, palettes, request, backendOnline, updateRequest, submit } =
    useGenerationStore();

  const mode = modes.find((m) => m.id === request.mode);

  return (
    <aside className="panel">
      <h2>Generate</h2>

      <div className="field">
        <label>Mode</label>
        <select
          value={request.mode}
          onChange={(e) => {
            const next = modes.find((m) => m.id === e.target.value);
            updateRequest({
              mode: e.target.value,
              ...(next
                ? {
                    width: next.default_width,
                    height: next.default_height,
                    transparent_background: next.transparent_background,
                  }
                : {}),
            });
          }}
        >
          {modes.map((m) => (
            <option key={m.id} value={m.id}>
              {m.name}
            </option>
          ))}
        </select>
        {mode && <label>{mode.description}</label>}
      </div>

      <div className="field">
        <label>Prompt</label>
        <textarea
          value={request.prompt}
          placeholder="a knight with a flaming sword"
          onChange={(e) => updateRequest({ prompt: e.target.value })}
        />
      </div>

      <div className="field">
        <label>Negative prompt</label>
        <input
          value={request.negative_prompt ?? ""}
          onChange={(e) => updateRequest({ negative_prompt: e.target.value })}
        />
      </div>

      <div className="field">
        <label>Style</label>
        <select value={request.style} onChange={(e) => updateRequest({ style: e.target.value })}>
          {styles.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </select>
      </div>

      <div className="field-row">
        <div className="field">
          <label>Width</label>
          <select
            value={request.width}
            onChange={(e) => updateRequest({ width: Number(e.target.value) })}
          >
            {SIZES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label>Height</label>
          <select
            value={request.height}
            onChange={(e) => updateRequest({ height: Number(e.target.value) })}
          >
            {SIZES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="field">
        <label>Palette</label>
        <select
          value={request.palette_id ?? ""}
          onChange={(e) => updateRequest({ palette_id: e.target.value || null })}
        >
          <option value="">Auto (extract)</option>
          {palettes.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
      </div>

      <div className="field-row">
        <div className="field">
          <label>Max colors</label>
          <input
            type="number"
            min={2}
            max={256}
            value={request.max_colors}
            onChange={(e) => updateRequest({ max_colors: Number(e.target.value) })}
          />
        </div>
        <div className="field">
          <label>Batch</label>
          <input
            type="number"
            min={1}
            max={16}
            value={request.batch_size}
            onChange={(e) => updateRequest({ batch_size: Number(e.target.value) })}
          />
        </div>
      </div>

      <div className="field-row">
        <div className="field">
          <label>Seed (blank = random)</label>
          <input
            type="number"
            value={request.seed ?? ""}
            onChange={(e) =>
              updateRequest({ seed: e.target.value === "" ? null : Number(e.target.value) })
            }
          />
        </div>
        <div className="field">
          <label>Dither</label>
          <select
            value={request.dither}
            onChange={(e) => updateRequest({ dither: e.target.value as "none" | "ordered" })}
          >
            <option value="none">None</option>
            <option value="ordered">Ordered</option>
          </select>
        </div>
      </div>

      <div className="field">
        <label>
          <input
            type="checkbox"
            checked={request.transparent_background}
            onChange={(e) => updateRequest({ transparent_background: e.target.checked })}
          />{" "}
          Transparent background
        </label>
      </div>

      <button
        className="primary-button"
        disabled={!backendOnline || !request.prompt?.trim()}
        onClick={() => void submit()}
      >
        Generate
      </button>
    </aside>
  );
}
