import { useEffect, useState } from "react";

import { EditorPanel } from "../features/editor/EditorPanel";
import { GenerationPanel } from "../features/generation/GenerationPanel";
import { ResultsPanel } from "../features/generation/ResultsPanel";
import { useGenerationStore } from "../state/generationStore";

type View = "generate" | "editor";

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
          <button
            className={view === "generate" ? "active" : ""}
            onClick={() => setView("generate")}
          >
            Generate
          </button>
          <button className={view === "editor" ? "active" : ""} onClick={() => setView("editor")}>
            Editor
          </button>
        </nav>
        <span className={`backend-status ${backendOnline ? "online" : "offline"}`}>
          {backendOnline
            ? `backend online${system ? ` · ${system.device.device}` : ""}`
            : "backend offline"}
        </span>
      </header>
      <main className="app-main">
        {view === "generate" ? (
          <div className="generate-layout">
            <GenerationPanel />
            <ResultsPanel />
          </div>
        ) : (
          <EditorPanel />
        )}
      </main>
    </div>
  );
}
