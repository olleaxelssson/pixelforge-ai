/** Typed HTTP client for the PixelForge backend. */
import { API_BASE_URL, WS_BASE_URL } from "../../shared/config";
import type {
  AnimationAction,
  AnimationResult,
  Character,
  CharacterIdentity,
  DriftResult,
  GenerationMode,
  GenerationRequest,
  Job,
  Palette,
  PaletteAnalysis,
  PluginReport,
  QAResponse,
  SceneGraph,
  StylePreset,
  SystemInfo,
} from "./types";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!response.ok) {
    const body = await response.text();
    throw new Error(`API ${response.status}: ${body}`);
  }
  return (await response.json()) as T;
}

export const api = {
  health: () => request<{ status: string }>("/api/health"),
  system: () => request<SystemInfo>("/api/system"),
  modes: () => request<GenerationMode[]>("/api/modes"),
  styles: () => request<StylePreset[]>("/api/styles"),
  palettes: () => request<Palette[]>("/api/palettes"),
  generate: (body: GenerationRequest) =>
    request<Job>("/api/generate", { method: "POST", body: JSON.stringify(body) }),
  jobs: () => request<Job[]>("/api/jobs"),
  job: (id: string) => request<Job>(`/api/jobs/${id}`),
  cancelJob: (id: string) => request<{ cancelled: boolean }>(`/api/jobs/${id}/cancel`, { method: "POST" }),
  imageUrl: (filename: string) => `${API_BASE_URL}/api/images/${filename}`,

  // Agentic layer (M7–M12) surfaced in the UI (M13).
  plan: (body: GenerationRequest) =>
    request<SceneGraph>("/api/plan", { method: "POST", body: JSON.stringify(body) }),

  qa: (body: {
    image_base64: string;
    max_colors?: number;
    transparent_background?: boolean;
    palette_id?: string | null;
    lighting_direction?: string | null;
    subject?: string | null;
    repair?: boolean;
    repair_loop?: boolean;
    max_iterations?: number;
  }) => request<QAResponse>("/api/qa", { method: "POST", body: JSON.stringify(body) }),

  paletteAnalysis: (paletteId: string) =>
    request<PaletteAnalysis>(`/api/palettes/${paletteId}/analysis`),

  characters: () => request<Character[]>("/api/characters"),
  createCharacter: (body: { name: string; identity: CharacterIdentity; palette_id?: string | null }) =>
    request<Character>("/api/characters", { method: "POST", body: JSON.stringify(body) }),
  deleteCharacter: (id: string) =>
    request<{ deleted: boolean }>(`/api/characters/${id}`, { method: "DELETE" }),
  addCharacterFrame: (id: string, body: { image_base64: string; label?: string }) =>
    request<Character>(`/api/characters/${id}/frames`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  characterDrift: (id: string, body: { image_base64: string }) =>
    request<DriftResult>(`/api/characters/${id}/drift`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  plugins: () => request<PluginReport>("/api/plugins"),

  animationActions: () => request<AnimationAction[]>("/api/animation/actions"),
  animate: (body: {
    prompt: string;
    action: string;
    mode?: string;
    width?: number;
    height?: number;
    seed?: number | null;
    palette_id?: string | null;
    max_colors?: number;
    frame_duration_ms?: number;
    run_qa?: boolean;
  }) =>
    request<AnimationResult>("/api/animation/generate", {
      method: "POST",
      body: JSON.stringify(body),
    }),
};

/** Subscribe to job progress over WebSocket; returns an unsubscribe function. */
export function subscribeToJob(jobId: string, onUpdate: (job: Job) => void): () => void {
  const socket = new WebSocket(`${WS_BASE_URL}/api/ws/jobs/${jobId}`);
  socket.onmessage = (event) => onUpdate(JSON.parse(event.data) as Job);
  return () => socket.close();
}
