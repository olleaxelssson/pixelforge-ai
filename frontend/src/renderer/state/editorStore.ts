/** Editor state: document, layers, tools, and snapshot-based undo/redo. */
import { create } from "zustand";

import { UNDO_HISTORY_LIMIT } from "../../shared/config";
import {
  cloneBuffer,
  createBuffer,
  drawEllipse,
  drawLine,
  drawRect,
  floodFill,
  hexToRgba,
  setPixel,
  shiftBuffer,
} from "../features/editor/pixelOps";

export type Tool =
  | "pencil"
  | "eraser"
  | "fill"
  | "line"
  | "rect"
  | "ellipse"
  | "select"
  | "move";

export interface Layer {
  id: string;
  name: string;
  visible: boolean;
  pixels: Uint8ClampedArray;
}

interface Snapshot {
  layers: Layer[];
  activeLayerIndex: number;
}

export interface EditorState {
  width: number;
  height: number;
  layers: Layer[];
  activeLayerIndex: number;
  tool: Tool;
  color: string;
  zoom: number;
  showGrid: boolean;
  onionSkin: boolean;
  undoStack: Snapshot[];
  redoStack: Snapshot[];

  newDocument: (width: number, height: number) => void;
  loadImageData: (data: Uint8ClampedArray, width: number, height: number) => void;
  setTool: (tool: Tool) => void;
  setColor: (color: string) => void;
  setZoom: (zoom: number) => void;
  toggleGrid: () => void;
  toggleOnionSkin: () => void;
  addLayer: () => void;
  removeLayer: (index: number) => void;
  setActiveLayer: (index: number) => void;
  toggleLayerVisibility: (index: number) => void;
  applyStroke: (points: Array<[number, number]>) => void;
  applyShape: (x0: number, y0: number, x1: number, y1: number, filled: boolean) => void;
  applyFill: (x: number, y: number) => void;
  applyMove: (dx: number, dy: number) => void;
  undo: () => void;
  redo: () => void;
}

let layerCounter = 0;
const makeLayer = (width: number, height: number, name?: string): Layer => ({
  id: `layer-${++layerCounter}`,
  name: name ?? `Layer ${layerCounter}`,
  visible: true,
  pixels: createBuffer(width, height),
});

const snapshot = (state: EditorState): Snapshot => ({
  layers: state.layers.map((layer) => ({ ...layer, pixels: cloneBuffer(layer.pixels) })),
  activeLayerIndex: state.activeLayerIndex,
});

export const useEditorStore = create<EditorState>((set, get) => {
  const pushUndo = () =>
    set((state) => ({
      undoStack: [...state.undoStack.slice(-UNDO_HISTORY_LIMIT + 1), snapshot(state)],
      redoStack: [],
    }));

  const updateActiveLayer = (pixels: Uint8ClampedArray) =>
    set((state) => ({
      layers: state.layers.map((layer, i) =>
        i === state.activeLayerIndex ? { ...layer, pixels } : layer,
      ),
    }));

  return {
    width: 32,
    height: 32,
    layers: [makeLayer(32, 32)],
    activeLayerIndex: 0,
    tool: "pencil",
    color: "#e45c10",
    zoom: 12,
    showGrid: true,
    onionSkin: false,
    undoStack: [],
    redoStack: [],

    newDocument: (width, height) =>
      set({
        width,
        height,
        layers: [makeLayer(width, height)],
        activeLayerIndex: 0,
        undoStack: [],
        redoStack: [],
      }),

    loadImageData: (data, width, height) =>
      set({
        width,
        height,
        layers: [{ ...makeLayer(width, height, "Imported"), pixels: cloneBuffer(data) }],
        activeLayerIndex: 0,
        undoStack: [],
        redoStack: [],
      }),

    setTool: (tool) => set({ tool }),
    setColor: (color) => set({ color }),
    setZoom: (zoom) => set({ zoom: Math.min(Math.max(zoom, 1), 48) }),
    toggleGrid: () => set((state) => ({ showGrid: !state.showGrid })),
    toggleOnionSkin: () => set((state) => ({ onionSkin: !state.onionSkin })),

    addLayer: () => {
      pushUndo();
      set((state) => ({
        layers: [...state.layers, makeLayer(state.width, state.height)],
        activeLayerIndex: state.layers.length,
      }));
    },

    removeLayer: (index) => {
      const { layers } = get();
      if (layers.length <= 1) return;
      pushUndo();
      set((state) => ({
        layers: state.layers.filter((_, i) => i !== index),
        activeLayerIndex: Math.max(0, Math.min(state.activeLayerIndex, layers.length - 2)),
      }));
    },

    setActiveLayer: (index) => set({ activeLayerIndex: index }),

    toggleLayerVisibility: (index) =>
      set((state) => ({
        layers: state.layers.map((layer, i) =>
          i === index ? { ...layer, visible: !layer.visible } : layer,
        ),
      })),

    applyStroke: (points) => {
      const state = get();
      pushUndo();
      const color =
        state.tool === "eraser"
          ? ([0, 0, 0, 0] as [number, number, number, number])
          : hexToRgba(state.color);
      const pixels = cloneBuffer(state.layers[state.activeLayerIndex].pixels);
      for (const [x, y] of points) setPixel(pixels, state.width, state.height, x, y, color);
      updateActiveLayer(pixels);
    },

    applyShape: (x0, y0, x1, y1, filled) => {
      const state = get();
      pushUndo();
      const color = hexToRgba(state.color);
      const source = state.layers[state.activeLayerIndex].pixels;
      let pixels: Uint8ClampedArray;
      if (state.tool === "line") {
        pixels = drawLine(source, state.width, state.height, x0, y0, x1, y1, color);
      } else if (state.tool === "rect") {
        pixels = drawRect(source, state.width, state.height, x0, y0, x1, y1, color, filled);
      } else {
        pixels = drawEllipse(source, state.width, state.height, x0, y0, x1, y1, color, filled);
      }
      updateActiveLayer(pixels);
    },

    applyFill: (x, y) => {
      const state = get();
      pushUndo();
      const pixels = floodFill(
        state.layers[state.activeLayerIndex].pixels,
        state.width,
        state.height,
        x,
        y,
        hexToRgba(state.color),
      );
      updateActiveLayer(pixels);
    },

    applyMove: (dx, dy) => {
      const state = get();
      pushUndo();
      updateActiveLayer(
        shiftBuffer(state.layers[state.activeLayerIndex].pixels, state.width, state.height, dx, dy),
      );
    },

    undo: () =>
      set((state) => {
        const previous = state.undoStack[state.undoStack.length - 1];
        if (!previous) return state;
        return {
          layers: previous.layers,
          activeLayerIndex: previous.activeLayerIndex,
          undoStack: state.undoStack.slice(0, -1),
          redoStack: [...state.redoStack, snapshot(state)],
        };
      }),

    redo: () =>
      set((state) => {
        const next = state.redoStack[state.redoStack.length - 1];
        if (!next) return state;
        return {
          layers: next.layers,
          activeLayerIndex: next.activeLayerIndex,
          redoStack: state.redoStack.slice(0, -1),
          undoStack: [...state.undoStack, snapshot(state)],
        };
      }),
  };
});
