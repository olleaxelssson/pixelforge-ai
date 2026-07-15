/** API types mirroring the backend pydantic models (keep in sync). */

export type JobStatus = "queued" | "running" | "completed" | "failed" | "cancelled";

export interface GenerationRequest {
  prompt: string;
  negative_prompt?: string;
  mode?: string;
  style?: string;
  width?: number;
  height?: number;
  seed?: number | null;
  batch_size?: number;
  palette_id?: string | null;
  max_colors?: number;
  dither?: "none" | "ordered";
  transparent_background?: boolean;
  outline_strength?: number;
  lighting_direction?: string;
  shading_style?: string;
  reference_image_base64?: string | null;
  reference_strength?: number;
}

export interface GeneratedImage {
  filename: string;
  width: number;
  height: number;
  seed: number;
  palette_hex: string[];
}

export interface Job {
  id: string;
  status: JobStatus;
  request: GenerationRequest;
  progress: { stage: string; percent: number };
  result: { images: GeneratedImage[] } | null;
  error: string | null;
}

export interface GenerationMode {
  id: string;
  name: string;
  description: string;
  default_width: number;
  default_height: number;
  transparent_background: boolean;
  accepts_reference_image: boolean;
}

export interface StylePreset {
  id: string;
  name: string;
  description: string;
  default_palette_id: string | null;
  default_max_colors: number | null;
  tags: string[];
}

export interface Palette {
  id: string;
  name: string;
  colors: string[];
  builtin: boolean;
}

export interface SystemInfo {
  version: string;
  backends: { name: string; available: boolean }[];
  device: { device: string; cuda: boolean; mps: boolean; gpu_name?: string };
  supported_sizes: number[];
}
