export type Verdict = "FOSSIL" | "FENCE" | "ACTIVE" | "UNKNOWN" | "PENDING";
export type Stance = "reason" | "status" | "counter" | "context";

export interface Evidence {
  id: string;
  acc: string;
  page: number;
  line_start: number;
  line_end: number;
  chunk: string;
  date: string | null;
  doc_type: string | null;
  title: string | null;
  stance: Stance;
  claim: string;
  quote: string;
  entities: string[];
  verified: boolean;
  suspicious: boolean;
}

export interface CostLine { label: string; qty: number; unit: string; unit_cost: number; amount: number; source: string }
export interface Cost {
  per_run_eur: number; runs_per_year: number; basis: string; annual_eur: number; lines: CostLine[]; formula: string; source: string;
}

export interface StrengthInfo {
  grade: "Strong" | "Moderate" | "Weak" | "Insufficient";
  score: number;
  breakdown: { label: string; points: number }[];
  documents: number;
  cited: string[];
  rule: string;
}

export interface Dependency { name: string; type: string; holds: boolean | null; evidence: string[]; note: string }
export interface CounterEv { claim: string; evidence: string[]; resolved: boolean; resolution: string }

export interface VerdictData {
  step_id: string;
  process: string;
  process_name: string;
  instruction: string;
  verdict: Exclude<Verdict, "PENDING">;
  proposed_verdict: string;
  reason: string;
  origin_year: number | null;
  origin_evidence: string[];
  chain: { claim: string; evidence: string[] }[];
  dependencies: Dependency[];
  counter_evidence: CounterEv[];
  open_questions: string[];
  first_seen: string | null;
  strength: StrengthInfo;
  guards: string[];
  evidence: Record<string, Evidence>;
  cost: Cost;
  provider: string;
  model: string;
  hops: number;
  duration_s: number;
  created_at: number;
  ignored_injection_docs: string[];
  stats?: { evidence_total: number; unverified_quotes: number; suspicious: number; uncited_removed: number };
}

export interface MapStep {
  id: string; seq: number; name: string; instruction: string; verdict: Verdict; strength: string | null; origin_year: number | null;
  first_seen: string | null; annual_cost_eur: number; reason: string;
}
export interface MapProcess { id: string; code: string; name: string; short: string; kind: string; revision: string; revision_date: string; steps: MapStep[] }
export interface MapData {
  plant: { name: string; site: string; synthetic: boolean; description: string };
  processes: MapProcess[];
  totals: Record<Verdict, number>;
  fossil_annual_eur: number;
  fence_annual_eur: number;
  computed_by: string[];
  mode: "amd" | "fixture";
}

export interface InvEvent {
  type: "start" | "hop" | "hop_started" | "concluding" | "verdict" | "warning" | "error" | "heartbeat" | "replay";
  n?: number;
  kind?: string;
  label?: string;
  query?: string | null;
  detail?: string;
  evidence?: Evidence[];
  documents?: string[];
  ignored_injection?: string[];
  verdict?: VerdictData;
  message?: string;
  provider?: string;
  model?: string;
  evidence_count?: number;
  recorded_at?: number;
  models?: Record<string, string>;
  hardware?: string;
  t?: number;
}

export interface DocLine { text: string; bbox?: number[] }
export interface DocPage { page: number; width: number; height: number; source: string; model: string | null; lines: DocLine[] }
export interface DocData {
  acc: string; pages: number; has_text_layer: number; title: string | null; doc_type: string | null; date: string | null;
  lang: string | null; summary: string; meta_source: string; text_source: string; injection_flag: number;
  refs: { own?: string[]; cited?: string[] }; entities: Record<string, string[]>; pages_data: DocPage[];
  catalog: Record<string, string>;
}
