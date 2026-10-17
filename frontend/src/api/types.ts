export type Source = "dictionary" | "algorithm";

export interface ZhChar {
  char: string;
  pinyin: string;
  meaning: string | null;
}

export interface ZhOption {
  rank: number;
  text: string;
  pinyin: string;
  chars: ZhChar[];
  source: Source;
  verified: boolean;
}

export interface JaOption {
  rank: number;
  text: string;
  romaji: string;
  source: Source;
  verified: boolean;
}

/** Respuesta de POST /api/names/convert (contrato 4.4 del plan + request_id). */
export interface Conversion {
  request_id: string;
  input: string;
  normalized: string;
  syllables: string[];
  zh: ZhOption[];
  ja: JaOption[];
}

export type ScriptKey = "zh" | "ja";

export interface Layout {
  paper: "A4" | "A5" | "carta" | "media_carta" | "oficio" | "medio_oficio" | "custom";
  width_mm: number | null;
  height_mm: number | null;
  landscape: boolean;
  margin_mm: number;
  char_size_mm: number;
  spacing_mm: number;
  orientation: "horizontal" | "vertical";
  dip_every_chars: number;
  auto_fit: boolean;
}

export interface JobRequestBody {
  request_id: string;
  script: ScriptKey;
  rank: number;
  layout: Layout;
}

export interface PathPreview {
  text: string;
  script: ScriptKey;
  layout: Layout;
  paper_width_mm: number;
  paper_height_mm: number;
  char_size_mm: number;
  strokes: number[][][];
  stroke_count: number;
  char_count: number;
  estimated_seconds: number;
}

export type JobStatus = "draft" | "queued" | "running" | "done" | "failed" | "cancelled";

export interface Job {
  id: string;
  request_id: string;
  script: ScriptKey;
  text: string;
  status: JobStatus;
  progress: number;
  layout: Layout;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  error: string | null;
  estimated_seconds: number | null;
}

export interface RequestItem {
  id: string;
  input_name: string;
  created_at: string;
  locale: string;
  zh_text: string | null;
  ja_text: string | null;
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export type Gender = "m" | "f" | "u";
export type Connotation = "positive" | "neutral" | "avoid";

export interface TranslitIn {
  script: ScriptKey;
  text: string;
  reading: string;
  rank: number;
}

export interface NameIn {
  display_name: string;
  gender: Gender;
  verified: boolean;
  transliterations: TranslitIn[];
}

export interface NameOut {
  id: number;
  name_es: string;
  display_name: string;
  gender: Gender;
  verified: boolean;
  transliterations: (TranslitIn & { id: number; verified: boolean })[];
  missing_glyphs: string[];
}

export interface SyllableIn {
  script: ScriptKey;
  syllable_es: string;
  output: string;
  reading: string;
  meaning: string | null;
  connotation: Connotation;
  gender_hint: Gender;
  score: number;
}

export interface SyllableOut extends SyllableIn {
  id: number;
}

export interface PendingItem {
  request_id: string;
  input_name: string;
  created_at: string;
  zh: { text: string; pinyin: string } | null;
  ja: { text: string; romaji: string } | null;
}

export type PointName = "origin" | "x_axis" | "y_axis" | "ink";
export type Xyz = [number, number, number];

export interface RobotConfig {
  driver: "mock" | "dobot";
  ip: string;
  user: number;
  tool: number;
  speed_factor: number;
  speed_l: number;
  accel_l: number;
  cp: number;
  lift_mm: number;
  press_depth_mm: number;
  r_deg: number;
  pencil_mode: boolean;
  dip_clearance_mm: number;
  dip_depth_mm: number;
  dip_dwell_s: number;
  origin: Xyz | null;
  x_axis: Xyz | null;
  y_axis: Xyz | null;
  ink: Xyz | null;
  calibrated?: boolean;
}

export interface RobotStatus {
  driver: string;
  reachable: boolean;
  mode: number | null;
  mode_name: string | null;
  enabled: boolean | null;
  alarm: boolean | null;
  pose: number[] | null;
  error: string | null;
}
