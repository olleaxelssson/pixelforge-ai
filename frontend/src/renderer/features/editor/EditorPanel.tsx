import { useCallback, useEffect, useRef, useState } from "react";

import { useEditorStore, Tool } from "../../state/editorStore";
import { useGenerationStore } from "../../state/generationStore";
import { mergeLayers } from "./pixelOps";

const TOOLS: Array<{ id: Tool; label: string; icon: string }> = [
  { id: "pencil", label: "Pencil (B)", icon: "✏" },
  { id: "eraser", label: "Eraser (E)", icon: "⌫" },
  { id: "fill", label: "Fill (G)", icon: "▨" },
  { id: "line", label: "Line (L)", icon: "╱" },
  { id: "rect", label: "Rectangle (R)", icon: "▭" },
  { id: "ellipse", label: "Ellipse (O)", icon: "◯" },
  { id: "select", label: "Select (M)", icon: "⬚" },
  { id: "move", label: "Move (V)", icon: "✥" },
];

export function EditorPanel() {
  const editor = useEditorStore();
  const palettes = useGenerationStore((state) => state.palettes);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [drag, setDrag] = useState<{ x: number; y: number } | null>(null);
  const strokeRef = useRef<Array<[number, number]>>([]);

  const render = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const context = canvas.getContext("2d");
    if (!context) return;
    context.clearRect(0, 0, canvas.width, canvas.height);
    const visible = editor.layers.filter((l) => l.visible).map((l) => l.pixels);
    const merged = mergeLayers(visible, editor.width, editor.height);
    const imageData = new ImageData(
      new Uint8ClampedArray(merged),
      editor.width,
      editor.height,
    );
    context.putImageData(imageData, 0, 0);
  }, [editor.layers, editor.width, editor.height]);

  useEffect(() => {
    render();
  }, [render]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.ctrlKey && event.key === "z" && !event.shiftKey) {
        event.preventDefault();
        editor.undo();
      } else if (event.ctrlKey && (event.key === "y" || (event.shiftKey && event.key === "Z"))) {
        event.preventDefault();
        editor.redo();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [editor]);

  const toGrid = (event: React.MouseEvent): [number, number] => {
    const rect = (event.target as HTMLCanvasElement).getBoundingClientRect();
    const x = Math.floor(((event.clientX - rect.left) / rect.width) * editor.width);
    const y = Math.floor(((event.clientY - rect.top) / rect.height) * editor.height);
    return [x, y];
  };

  const onMouseDown = (event: React.MouseEvent) => {
    const [x, y] = toGrid(event);
    if (editor.tool === "fill") {
      editor.applyFill(x, y);
    } else if (editor.tool === "pencil" || editor.tool === "eraser") {
      strokeRef.current = [[x, y]];
      setDrag({ x, y });
    } else {
      setDrag({ x, y });
    }
  };

  const onMouseMove = (event: React.MouseEvent) => {
    if (!drag) return;
    if (editor.tool === "pencil" || editor.tool === "eraser") {
      const [x, y] = toGrid(event);
      strokeRef.current.push([x, y]);
      // Live preview: apply incrementally on release only (kept simple).
    }
  };

  const onMouseUp = (event: React.MouseEvent) => {
    if (!drag) return;
    const [x, y] = toGrid(event);
    if (editor.tool === "pencil" || editor.tool === "eraser") {
      editor.applyStroke([...strokeRef.current, [x, y]]);
      strokeRef.current = [];
    } else if (["line", "rect", "ellipse"].includes(editor.tool)) {
      editor.applyShape(drag.x, drag.y, x, y, event.shiftKey);
    } else if (editor.tool === "move") {
      editor.applyMove(x - drag.x, y - drag.y);
    }
    setDrag(null);
  };

  return (
    <div className="editor-layout">
      <div className="toolbar">
        {TOOLS.map((tool) => (
          <button
            key={tool.id}
            className={`tool-button ${editor.tool === tool.id ? "active" : ""}`}
            title={tool.label}
            onClick={() => editor.setTool(tool.id)}
          >
            {tool.icon}
          </button>
        ))}
        <button className="tool-button" title="Undo (Ctrl+Z)" onClick={editor.undo}>
          ↶
        </button>
        <button className="tool-button" title="Redo (Ctrl+Y)" onClick={editor.redo}>
          ↷
        </button>
        <button
          className={`tool-button ${editor.showGrid ? "active" : ""}`}
          title="Toggle grid"
          onClick={editor.toggleGrid}
        >
          #
        </button>
      </div>

      <div className="canvas-area">
        <canvas
          ref={canvasRef}
          className="editor-canvas"
          width={editor.width}
          height={editor.height}
          style={{
            width: editor.width * editor.zoom,
            height: editor.height * editor.zoom,
          }}
          onMouseDown={onMouseDown}
          onMouseMove={onMouseMove}
          onMouseUp={onMouseUp}
          onWheel={(event) => {
            if (event.ctrlKey) editor.setZoom(editor.zoom + (event.deltaY < 0 ? 1 : -1));
          }}
        />
      </div>

      <div className="sidebar">
        <div>
          <h3>Color</h3>
          <input
            type="color"
            value={editor.color}
            onChange={(e) => editor.setColor(e.target.value)}
          />
        </div>

        <div>
          <h3>Palette</h3>
          <div className="palette-swatches">
            {(palettes[0]?.colors ?? []).map((color) => (
              <div
                key={color}
                className={`swatch ${editor.color === color ? "selected" : ""}`}
                style={{ background: color }}
                onClick={() => editor.setColor(color)}
              />
            ))}
          </div>
        </div>

        <div>
          <h3>Layers</h3>
          {editor.layers.map((layer, index) => (
            <div
              key={layer.id}
              className={`layer-row ${index === editor.activeLayerIndex ? "active" : ""}`}
              onClick={() => editor.setActiveLayer(index)}
            >
              <input
                type="checkbox"
                checked={layer.visible}
                onChange={() => editor.toggleLayerVisibility(index)}
                onClick={(e) => e.stopPropagation()}
              />
              <span>{layer.name}</span>
            </div>
          ))}
          <button className="small-button" onClick={editor.addLayer}>
            + Add layer
          </button>
        </div>

        <div>
          <h3>Canvas</h3>
          <button className="small-button" onClick={() => editor.newDocument(32, 32)}>
            New 32×32
          </button>{" "}
          <button className="small-button" onClick={() => editor.newDocument(64, 64)}>
            New 64×64
          </button>
          <div style={{ marginTop: 8, fontSize: 12, color: "var(--text-dim)" }}>
            {editor.width}×{editor.height} · zoom {editor.zoom}x (Ctrl+scroll)
          </div>
        </div>
      </div>
    </div>
  );
}
