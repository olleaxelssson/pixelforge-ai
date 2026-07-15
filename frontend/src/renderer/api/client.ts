/** Typed HTTP client for the PixelForge backend. */
import { API_BASE_URL, WS_BASE_URL } from "../../shared/config";
import type {
  GenerationMode,
  GenerationRequest,
  Job,
  Palette,
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
};

/** Subscribe to job progress over WebSocket; returns an unsubscribe function. */
export function subscribeToJob(jobId: string, onUpdate: (job: Job) => void): () => void {
  const socket = new WebSocket(`${WS_BASE_URL}/api/ws/jobs/${jobId}`);
  socket.onmessage = (event) => onUpdate(JSON.parse(event.data) as Job);
  return () => socket.close();
}
