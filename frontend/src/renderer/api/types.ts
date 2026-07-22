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

export interface Critique {
  backend: string;
  subject: string | null;
  subject_match: number;
  appeal: number;
  verdict: string;
  notes: string[];
}

export interface QAReport {
  width: number;
  height: number;
  passed: boolean;
  scores: QAScores;
  findings: Finding[];
  critique: Critique | null;
}

export interface RepairAttempt {
  iteration: number;
  regions: number;
  pixels: number;
  overall_before: number;
  overall_after: number;
  accepted: boolean;
}

export interface RepairLoopReport {
  iterations: number;
  improved: boolean;
  initial: QAReport;
  final: QAReport;
  attempts: RepairAttempt[];
}

export interface QAResponse {
  report: QAReport;
  repaired_image_base64: string | null;
  repair_loop: RepairLoopReport | null;
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

// --- Animation (M3/M18) ---

export interface AnimationAction {
  id: string;
  name: string;
  frame_count: number;
  frame_descriptions: string[];
  loop: boolean;
}

export interface AnimationFrame {
  index: number;
  filename: string;
  seed: number;
  description: string;
  qa: QAScores | null;
  consistency: number | null;
}

export interface AnimationResult {
  action: string;
  action_name: string;
  loop: boolean;
  frame_duration_ms: number;
  palette_hex: string[];
  frames: AnimationFrame[];
  gif_filename: string;
  sheet_filename: string;
  mean_consistency: number | null;
  min_consistency: number | null;
  consistent: boolean | null;
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

// --- Dataset & LoRA-training toolkit (M4/M21) ---

export interface DatasetItem {
  name: string;
  valid: boolean;
  width: number;
  height: number;
  issues: string[];
  phash: string;
  caption: string;
  tags: string[];
  duplicate_of: string | null;
}

export interface DuplicateCluster {
  representative: string;
  members: string[];
  distance: number;
}

export interface LoraConfig {
  base_model: string;
  resolution: number;
  network_dim: number;
  network_alpha: number;
  learning_rate: number;
  train_batch_size: number;
  max_train_epochs: number;
  optimizer: string;
  lr_scheduler: string;
  mixed_precision: string;
  trigger_word: string;
  image_count: number;
}

export interface DatasetReport {
  root: string;
  total: number;
  valid_count: number;
  invalid_count: number;
  duplicate_count: number;
  items: DatasetItem[];
  clusters: DuplicateCluster[];
  lora_config: LoraConfig;
  manifest: Record<string, unknown>[];
  manifest_path: string | null;
  config_path: string | null;
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
