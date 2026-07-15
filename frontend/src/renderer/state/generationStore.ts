/** Generation state: catalogs, request form, job queue and results. */
import { create } from "zustand";

import { api, subscribeToJob } from "../api/client";
import type {
  GenerationMode,
  GenerationRequest,
  Job,
  Palette,
  StylePreset,
  SystemInfo,
} from "../api/types";

export interface GenerationState {
  modes: GenerationMode[];
  styles: StylePreset[];
  palettes: Palette[];
  system: SystemInfo | null;
  jobs: Record<string, Job>;
  jobOrder: string[];
  request: GenerationRequest;
  backendOnline: boolean;

  loadCatalogs: () => Promise<void>;
  updateRequest: (patch: Partial<GenerationRequest>) => void;
  submit: () => Promise<void>;
  cancel: (jobId: string) => Promise<void>;
}

export const useGenerationStore = create<GenerationState>((set, get) => ({
  modes: [],
  styles: [],
  palettes: [],
  system: null,
  jobs: {},
  jobOrder: [],
  backendOnline: false,
  request: {
    prompt: "",
    negative_prompt: "",
    mode: "text-to-pixel",
    style: "modern-indie",
    width: 32,
    height: 32,
    seed: null,
    batch_size: 1,
    palette_id: null,
    max_colors: 16,
    dither: "none",
    transparent_background: true,
  },

  loadCatalogs: async () => {
    try {
      const [modes, styles, palettes, system] = await Promise.all([
        api.modes(),
        api.styles(),
        api.palettes(),
        api.system(),
      ]);
      set({ modes, styles, palettes, system, backendOnline: true });
    } catch {
      set({ backendOnline: false });
    }
  },

  updateRequest: (patch) => set((state) => ({ request: { ...state.request, ...patch } })),

  submit: async () => {
    const { request } = get();
    if (!request.prompt.trim()) return;
    const job = await api.generate(request);
    set((state) => ({
      jobs: { ...state.jobs, [job.id]: job },
      jobOrder: [job.id, ...state.jobOrder],
    }));
    const unsubscribe = subscribeToJob(job.id, (update) => {
      set((state) => ({ jobs: { ...state.jobs, [update.id]: update } }));
      if (["completed", "failed", "cancelled"].includes(update.status)) unsubscribe();
    });
  },

  cancel: async (jobId) => {
    await api.cancelJob(jobId);
    const job = await api.job(jobId);
    set((state) => ({ jobs: { ...state.jobs, [jobId]: job } }));
  },
}));
