/** Character-memory state (D-011): the stored character list and its mutations. */
import { create } from "zustand";

import { api } from "../api/client";
import type { Character, DriftResult } from "../api/types";

export interface CharactersState {
  characters: Character[];
  selectedId: string | null;
  loading: boolean;
  error: string | null;
  drift: Record<string, DriftResult>;

  load: () => Promise<void>;
  select: (id: string | null) => void;
  create: (name: string, subject: string, paletteId: string | null) => Promise<void>;
  remove: (id: string) => Promise<void>;
  addFrame: (id: string, imageBase64: string, label: string) => Promise<void>;
  checkDrift: (id: string, imageBase64: string) => Promise<void>;
}

function message(e: unknown): string {
  return e instanceof Error ? e.message : "request failed";
}

export const useCharactersStore = create<CharactersState>((set) => ({
  characters: [],
  selectedId: null,
  loading: false,
  error: null,
  drift: {},

  load: async () => {
    set({ loading: true, error: null });
    try {
      set({ characters: await api.characters(), loading: false });
    } catch (e) {
      set({ error: message(e), loading: false });
    }
  },

  select: (id) => set({ selectedId: id }),

  create: async (name, subject, paletteId) => {
    set({ error: null });
    try {
      const character = await api.createCharacter({
        name,
        identity: {
          subject,
          kind: "character",
          parts: [],
          materials: [],
          proportions: "",
          silhouette: "",
          bible: "",
        },
        palette_id: paletteId,
      });
      set((state) => ({ characters: [...state.characters, character], selectedId: character.id }));
    } catch (e) {
      set({ error: message(e) });
    }
  },

  remove: async (id) => {
    set({ error: null });
    try {
      await api.deleteCharacter(id);
      set((state) => ({
        characters: state.characters.filter((c) => c.id !== id),
        selectedId: state.selectedId === id ? null : state.selectedId,
      }));
    } catch (e) {
      set({ error: message(e) });
    }
  },

  addFrame: async (id, imageBase64, label) => {
    set({ error: null });
    try {
      const updated = await api.addCharacterFrame(id, { image_base64: imageBase64, label });
      set((state) => ({
        characters: state.characters.map((c) => (c.id === id ? updated : c)),
      }));
    } catch (e) {
      set({ error: message(e) });
    }
  },

  checkDrift: async (id, imageBase64) => {
    set({ error: null });
    try {
      const result = await api.characterDrift(id, { image_base64: imageBase64 });
      set((state) => ({ drift: { ...state.drift, [id]: result } }));
    } catch (e) {
      set({ error: message(e) });
    }
  },
}));
