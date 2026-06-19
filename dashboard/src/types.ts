export interface ScoreResult {
  scorer: string;
  score: number;
  weight: number;
  passed: boolean;
  detail: string;
}

export interface CaseResult {
  case_id: string;
  weighted_score: number;
  passed: boolean;
  cost_usd: number;
  latency_ms: number;
}

export interface Target {
  target_id: string;
  provider: string;
  model: string;
  mean_score: number;
  pass_rate: number;
  total_cost_usd: number;
  mean_latency_ms: number;
  total_tokens: number;
  cases: CaseResult[];
}

export interface Run {
  run_id: string;
  suite_name: string;
  created_at: string;
  notes: string;
  git_sha: string | null;
  targets: Target[];
}
