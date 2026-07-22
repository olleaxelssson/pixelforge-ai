import { useEffect, useState } from "react";

import { AnimationPanel } from "../features/animation/AnimationPanel";
import { CharactersPanel } from "../features/characters/CharactersPanel";
import { DatasetPanel } from "../features/dataset/DatasetPanel";
import { EditorPanel } from "../features/editor/EditorPanel";
import { GenerationPanel } from "../features/generation/GenerationPanel";
import { ResultsPanel } from "../features/generation/ResultsPanel";
import { PalettePanel } from "../features/palettes/PalettePanel";
import { QAPanel } from "../features/qa/QAPanel";
import { TilesetPanel } from "../features/tileset/TilesetPanel";
import { useGenerationStore } from "../state/generationStore";

type View =
  | "generate"
  | "editor"
  | "animation"
  | "tileset"
  | "qa"
  | "characters"
  | "palettes"
  | "dataset";

const VIEWS: { id: View; label: string }[] = [
  { id: "generate", label: "Generate" },
  { id: "editor", label: "Editor" },
  { id: "animation", label: "Animation" },
  { id: "tileset", label: "Tileset" },
  { id: "qa", label: "QA" },
  { id: "characters", label: "Characters" },
  { id: "palettes", label: "Palette Lab" },
  { id: "dataset", label: "Dataset" },
];

export function App() {
  const [view, setView] = useState<View>("generate");
  const backendOnline = useGenerationStore((state) => state.backendOnline);
  const system = useGenerationStore((state) => state.system);
  const loadCatalogs = useGenerationStore((state) => state.loadCatalogs);

  useEffect(() => {
    void loadCatalogs();
    const interval = setInterval(() => {
      if (!useGenerationStore.getState().backendOnline) void loadCatalogs();
    }, 3000);
    return () => clearInterval(interval);
  }, [loadCatalogs]);

  return (
    <div className="app">
      <header className="app-header">
        <span className="app-title">PixelForge AI</span>
        <nav className="app-nav">
          {VIEWS.map((v) => (
            <button
              key={v.id}
              className={view === v.id ? "active" : ""}
              onClick={() => setView(v.id)}
            >
              {v.label}
            </button>
          ))}
        </nav>
        <span className={`backend-status ${backendOnline ? "online" : "offline"}`}>
          {backendOnline
            ? `backend online${system ? ` · ${system.device.device}` : ""}`
            : "backend offline"}
        </span>
      </header>
      <main className="app-main">
        {view === "generate" && (
          <div className="generate-layout">
            <GenerationPanel />
            <ResultsPanel />
          </div>
        )}
        {view === "editor" && <EditorPanel />}
        {view === "animation" && <AnimationPanel />}
        {view === "tileset" && <TilesetPanel />}
        {view === "qa" && <QAPanel />}
        {view === "characters" && <CharactersPanel />}
        {view === "palettes" && <PalettePanel />}
        {view === "dataset" && <DatasetPanel />}
      </main>
    </div>
  );
}
