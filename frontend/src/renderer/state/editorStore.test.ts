import { beforeEach, describe, expect, it } from "vitest";

import { getPixel } from "../features/editor/pixelOps";
import { useEditorStore } from "./editorStore";

describe("editorStore", () => {
  beforeEach(() => {
    useEditorStore.getState().newDocument(8, 8);
    useEditorStore.getState().setTool("pencil");
  });

  it("applies pencil strokes", () => {
    const store = useEditorStore.getState();
    store.setColor("#ff0000");
    store.applyStroke([
      [1, 1],
      [2, 2],
    ]);
    const { layers, activeLayerIndex } = useEditorStore.getState();
    expect(getPixel(layers[activeLayerIndex].pixels, 8, 1, 1)).toEqual([255, 0, 0, 255]);
  });

  it("undo and redo restore pixel state", () => {
    const store = useEditorStore.getState();
    store.setColor("#00ff00");
    store.applyStroke([[3, 3]]);
    useEditorStore.getState().undo();
    let state = useEditorStore.getState();
    expect(getPixel(state.layers[0].pixels, 8, 3, 3)[3]).toBe(0);
    state.redo();
    state = useEditorStore.getState();
    expect(getPixel(state.layers[0].pixels, 8, 3, 3)).toEqual([0, 255, 0, 255]);
  });

  it("eraser clears pixels", () => {
    const store = useEditorStore.getState();
    store.applyStroke([[4, 4]]);
    store.setTool("eraser");
    useEditorStore.getState().applyStroke([[4, 4]]);
    expect(getPixel(useEditorStore.getState().layers[0].pixels, 8, 4, 4)[3]).toBe(0);
  });

  it("manages layers", () => {
    const store = useEditorStore.getState();
    store.addLayer();
    expect(useEditorStore.getState().layers.length).toBe(2);
    expect(useEditorStore.getState().activeLayerIndex).toBe(1);
    useEditorStore.getState().removeLayer(1);
    expect(useEditorStore.getState().layers.length).toBe(1);
    useEditorStore.getState().removeLayer(0); // last layer cannot be removed
    expect(useEditorStore.getState().layers.length).toBe(1);
  });

  it("move shifts the active layer", () => {
    const store = useEditorStore.getState();
    store.setColor("#0000ff");
    store.applyStroke([[0, 0]]);
    useEditorStore.getState().applyMove(2, 3);
    const pixels = useEditorStore.getState().layers[0].pixels;
    expect(getPixel(pixels, 8, 2, 3)).toEqual([0, 0, 255, 255]);
    expect(getPixel(pixels, 8, 0, 0)[3]).toBe(0);
  });
});
