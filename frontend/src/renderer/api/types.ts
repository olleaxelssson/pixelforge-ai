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
  character_id?: string | null;
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

// --- Scene Graph (D-009/D-010) — the plan a request compiles to ---

export interface Material {
  name: string;
  kind: string;
  description: string;
  specular: boolean;
  dither_ok: boolean;
  ramp_size: number;
}

export interface Part {
  name: string;
  description: string;
  z_order: number;
  material: string | null;
  palette_index_refs: number[];
}

export interface SceneEntity {
  kind: string;
  subject: string;
  intent: string;
  parts: Part[];
  materials: Material[];
}

export interface PalettePlan {
  palette_id: string | null;
  max_colors: number;
  locked: boolean;
}

export interface Lighting {
  direction: string;
  intensity: number;
  single_source: boolean;
  rim_light: boolean;
}

export interface Composition {
  framing: string;
  margin_fraction: number;
  focal_point: string;
  balance: string;
}

export interface SilhouettePlan {
  grid: string[];
  notes: string;
}

export interface Provenance {
  user_prompt: string;
  expanded_prompt: string;
  negative_prompt: string;
  seed: number | null;
  mode: string;
  style: string;
  planning_backend: string;
  agent_trace: string[];
  model_versions: Record<string, string>;
}

export interface SceneGraph {
  schema_version: number;
  id: string;
  entity: SceneEntity;
  palette: PalettePlan;
  lighting: Lighting;
  composition: Composition;
  silhouette: SilhouettePlan | null;
  provenance: Provenance;
  tags: string[];
}

// --- Pixel QA (D-013) ---

export type FindingSeverity = "info" | "warning" | "error";

export interface Region {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface Finding {
  detector: string;
  severity: FindingSeverity;
  message: string;
  region: Region | null;
}

export interface QAScores {
  readability: number;
  palette: number;
  contrast: number;
  silhouette: number;
  cleanliness: number;
  overall: number;
}

export interface QAReport {
  width: number;
  height: number;
  passed: boolean;
  scores: QAScores;
  findings: Finding[];
}

export interface QAResponse {
  report: QAReport;
  repaired_image_base64: string | null;
}

// --- Palette intelligence (D-012) ---

export interface ColorPair {
  a: string;
  b: string;
  delta_e: number;
  contrast_ratio: number | null;
}

export interface ContrastReport {
  max_contrast_ratio: number;
  min_delta_e: number;
  mean_delta_e: number;
  low_contrast_pairs: ColorPair[];
}

export interface CvdReport {
  vision: string;
  confusable_pairs: ColorPair[];
  simulated_hex: string[];
}

export interface Suggestion {
  code: string;
  severity: string;
  message: string;
}

export interface PaletteAnalysis {
  palette_id: string;
  color_count: number;
  ramps: string[][];
  duplicates: ColorPair[];
  contrast: ContrastReport;
  cvd: CvdReport[];
  readability_score: number;
  suggestions: Suggestion[];
}

// --- Character memory (D-011) ---

export interface CharacterIdentity {
  subject: string;
  kind: string;
  parts: Part[];
  materials: Material[];
  proportions: string;
  silhouette: string;
  bible: string;
}

export interface ReferenceFrame {
  filename: string;
  label: string;
}

export interface Character {
  id: string;
  name: string;
  identity: CharacterIdentity;
  palette_id: string | null;
  reference_frames: ReferenceFrame[];
  embedding: number[];
  embedding_backend: string;
  created_at: number;
  updated_at: number;
}

export interface DriftResult {
  character_id: string;
  similarity: number;
  threshold: number;
  consistent: boolean;
}

// --- Plugin SDK (D-014) ---

export interface PluginManifest {
  name: string;
  version: string;
  author: string;
  description: string;
  api_version: string;
  capabilities: string[];
}

export interface LoadedPlugin {
  name: string;
  version: string;
  manifest: PluginManifest;
  components: string[];
  errors: string[];
}

export interface SkippedPlugin {
  name: string;
  reason: string;
}

export interface PluginReport {
  enabled: boolean;
  api_version: string;
  loaded: LoadedPlugin[];
  skipped: SkippedPlugin[];
}
