import { useMemo, useRef, useState } from "react";

import { api, downloadProject } from "../../api/client";
import { fileToBase64, imageUrlToBase64 } from "../../api/image";
import { useGenerationStore } from "../../state/generationStore";
import { recentResults } from "../generation/recentResults";
import { isDirty, projectSummary, sanitizeName, type SummaryRow } from "./projectView";

/** The Project menu in the header: Save/Open a portable ``.pforge`` + an unsaved-changes dot. */
export function ProjectBar() {
  const jobs = useGenerationStore((state) => state.jobs);
  const jobOrder = useGenerationStore((state) => state.jobOrder);
  const backendOnline = useGenerationStore((state) => state.backendOnline);

  const [name, setName] = useState("Untitled Project");
  const [savedCount, setSavedCount] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [opened, setOpened] = useState<SummaryRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const createdAt = useRef(Math.floor(Date.now() / 1000)); // stable → re-saves are byte-identical
  const fileInput = useRef<HTMLInputElement>(null);

  const results = useMemo(() => recentResults(jobs, jobOrder, 200), [jobs, jobOrder]);
  const dirty = isDirty(results.length, savedCount);

  const save = async () => {
    setBusy(true);
    setError(null);
    try {
      const sprites = await Promise.all(
        results.map(async (r) => ({
          name: r.filename,
          image_base64: await imageUrlToBase64(api.imageUrl(r.filename)),
        })),
      );
      await downloadProject({ name: sanitizeName(name), created_at: createdAt.current, sprites });
      setSavedCount(results.length);
    } catch (e) {
      setError(e instanceof Error ? e.message : "save failed");
    } finally {
      setBusy(false);
    }
  };

  const open = async (file: File | undefined) => {
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const base64 = await fileToBase64(file);
      const loaded = await api.loadProject(base64);
      setName(loaded.manifest.name);
      setOpened(projectSummary(loaded.manifest));
      setSavedCount(results.length); // opening establishes a clean baseline
    } catch (e) {
      setError(e instanceof Error ? e.message : "open failed");
    } finally {
      setBusy(false);
      if (fileInput.current) fileInput.current.value = "";
    }
  };

  return (
    <div className="project-bar">
      <input
        className="project-name"
        value={name}
        onChange={(e) => setName(e.target.value)}
        aria-label="Project name"
      />
      {dirty && <span className="project-dirty" title="unsaved changes">&bull;</span>}
      <button
        className="small-button"
        disabled={!backendOnline || busy}
        onClick={() => void save()}
      >
        Save
      </button>
      <button
        className="small-button"
        disabled={!backendOnline || busy}
        onClick={() => fileInput.current?.click()}
      >
        Open
      </button>
      <input
        ref={fileInput}
        type="file"
        accept=".pforge"
        style={{ display: "none" }}
        onChange={(e) => void open(e.target.files?.[0])}
      />
      {opened && (
        <span className="project-opened">
          opened: {opened.find((r) => r.label === "sprites")?.value} sprites
        </span>
      )}
      {error && <span className="project-error">{error}</span>}
    </div>
  );
}
