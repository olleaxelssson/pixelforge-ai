import { useEffect, useState } from "react";

import { api } from "../../api/client";
import { fileToBase64 } from "../../api/image";
import { useCharactersStore } from "../../state/charactersStore";
import { useGenerationStore } from "../../state/generationStore";

function CreateForm() {
  const palettes = useGenerationStore((state) => state.palettes);
  const create = useCharactersStore((state) => state.create);
  const [name, setName] = useState("");
  const [subject, setSubject] = useState("");
  const [paletteId, setPaletteId] = useState("");

  const submit = async () => {
    if (!name.trim() || !subject.trim()) return;
    await create(name.trim(), subject.trim(), paletteId || null);
    setName("");
    setSubject("");
    setPaletteId("");
  };

  return (
    <div className="character-create">
      <h3>New character</h3>
      <div className="field">
        <label>Name</label>
        <input value={name} placeholder="Elias" onChange={(e) => setName(e.target.value)} />
      </div>
      <div className="field">
        <label>Subject (identity)</label>
        <textarea
          value={subject}
          placeholder="Captain Elias, a grizzled veteran knight"
          onChange={(e) => setSubject(e.target.value)}
        />
      </div>
      <div className="field">
        <label>Locked palette (optional)</label>
        <select value={paletteId} onChange={(e) => setPaletteId(e.target.value)}>
          <option value="">None</option>
          {palettes.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
      </div>
      <button
        className="primary-button"
        disabled={!name.trim() || !subject.trim()}
        onClick={() => void submit()}
      >
        Create character
      </button>
    </div>
  );
}

function DriftBadge({ characterId }: { characterId: string }) {
  const drift = useCharactersStore((state) => state.drift[characterId]);
  if (!drift) return null;
  const percent = Math.round(drift.similarity * 100);
  return (
    <div className={`drift-badge ${drift.consistent ? "consistent" : "drifted"}`}>
      identity {percent}% · {drift.consistent ? "consistent" : "drifted"} (gate{" "}
      {Math.round(drift.threshold * 100)}%)
    </div>
  );
}

function CharacterDetail({ id }: { id: string }) {
  const character = useCharactersStore((state) => state.characters.find((c) => c.id === id));
  const addFrame = useCharactersStore((state) => state.addFrame);
  const checkDrift = useCharactersStore((state) => state.checkDrift);
  const remove = useCharactersStore((state) => state.remove);
  const [label, setLabel] = useState("passport");

  if (!character) return null;

  const uploadFrame = async (file: File | undefined) => {
    if (!file) return;
    await addFrame(id, await fileToBase64(file), label);
  };

  const driftFrom = async (file: File | undefined) => {
    if (!file) return;
    await checkDrift(id, await fileToBase64(file));
  };

  return (
    <div className="character-detail">
      <div className="character-detail-head">
        <h3>{character.name}</h3>
        <button className="small-button danger" onClick={() => void remove(id)}>
          Delete
        </button>
      </div>
      <p className="character-subject">{character.identity.subject}</p>
      <div className="character-meta">
        <span>palette: {character.palette_id ?? "none"}</span>
        <span>embedding: {character.embedding_backend}</span>
        <span>frames: {character.reference_frames.length}</span>
      </div>

      {character.reference_frames.length > 0 && (
        <div className="frame-strip">
          {character.reference_frames.map((frame) => (
            <figure key={frame.filename}>
              <img
                className="frame-thumb"
                src={api.imageUrl(frame.filename)}
                alt={frame.label}
                title={frame.label}
              />
              <figcaption>{frame.label}</figcaption>
            </figure>
          ))}
        </div>
      )}

      <div className="field-row">
        <div className="field">
          <label>Frame label</label>
          <select value={label} onChange={(e) => setLabel(e.target.value)}>
            <option value="passport">passport (anchors identity)</option>
            <option value="variant">variant</option>
          </select>
        </div>
        <div className="field">
          <label>Add reference frame</label>
          <input
            type="file"
            accept="image/*"
            onChange={(e) => void uploadFrame(e.target.files?.[0])}
          />
        </div>
      </div>

      <div className="field">
        <label>Check drift against a sprite</label>
        <input
          type="file"
          accept="image/*"
          disabled={character.embedding.length === 0}
          onChange={(e) => void driftFrom(e.target.files?.[0])}
        />
        {character.embedding.length === 0 && (
          <label>Add a &ldquo;passport&rdquo; frame first to anchor the identity embedding.</label>
        )}
      </div>

      <DriftBadge characterId={id} />
    </div>
  );
}

export function CharactersPanel() {
  const characters = useCharactersStore((state) => state.characters);
  const selectedId = useCharactersStore((state) => state.selectedId);
  const error = useCharactersStore((state) => state.error);
  const load = useCharactersStore((state) => state.load);
  const select = useCharactersStore((state) => state.select);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div className="studio-panel">
      <aside className="panel character-list">
        <h2>Characters</h2>
        {characters.length === 0 && (
          <p style={{ color: "var(--text-dim)" }}>
            No characters yet. Create one to lock an identity across generations.
          </p>
        )}
        <ul className="character-items">
          {characters.map((c) => (
            <li key={c.id}>
              <button
                className={c.id === selectedId ? "active" : ""}
                onClick={() => select(c.id)}
              >
                <span className="character-name">{c.name}</span>
                <span className="character-hint">{c.reference_frames.length} frame(s)</span>
              </button>
            </li>
          ))}
        </ul>
        <CreateForm />
        {error && <div className="error-text">{error}</div>}
      </aside>

      <section className="results">
        {selectedId ? (
          <CharacterDetail id={selectedId} />
        ) : (
          <p style={{ color: "var(--text-dim)" }}>
            Select a character to manage reference frames and check drift.
          </p>
        )}
      </section>
    </div>
  );
}
