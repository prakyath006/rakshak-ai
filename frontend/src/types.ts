export interface DisputeSummary {
  case_id: string;
  dispute_id: string;
  title: string;
  category: string;
  reason_code: string;
  reason_description: string;
  amount: number;
  currency: string;
  phase: string;
  status: string;
  respond_by: string;
  customer_name: string;
  expected_decision: string;
}

export interface EvidenceNode {
  evidence_id: string;
  type: string;
  source: string;
  reliability: number;
  supports: string;
  razorpay_field: string;
  content: Record<string, unknown>;
  timestamp?: string;
}

export interface ExtractionSignal {
  communication_id: string;
  signal: string;
  quote: string;
  confidence: number | null;
  reasoning: string | null;
  direction?: string;
}

export interface AdvisoryFlag {
  flag: string;
  severity: 'blocking' | 'caution' | 'info';
  signal: string;
  communication_id: string;
  quote: string;
  detail: string;
}

export interface ExtractionResult {
  enabled: boolean;
  model: string | null;
  reason: string | null;
  claim_summary: string | null;
  signals: ExtractionSignal[];
  rejected_signals: Array<{ signal?: string; quote?: string; rejection: string }>;
  quote_verification: {
    proposed: number;
    verbatim: number;
    rejected: number;
    neutral: number;
    grounding_rate: number | null;
  };
  advisory_flags: AdvisoryFlag[];
}

export interface DraftVerification {
  tokens_checked: number;
  unsupported: Array<{ token: string; kind: string; detail: string }>;
  passed: boolean;
  grounding_rate: number | null;
}

export interface Rebuttal {
  explanation: string;
  template_explanation?: string;
  claims: Array<{ claim: string; evidence_ids: string[]; confidence: number; is_grounded: boolean }>;
  grounded_claims_rate: number;
  claims_check_structurally_guaranteed?: boolean;
  narrative_source?: 'template' | 'llm' | 'template_after_llm_rejected';
  llm_draft?: {
    attempted: boolean;
    accepted: boolean;
    model: string | null;
    reason: string | null;
    verification: DraftVerification | null;
    rejected_draft: string | null;
  };
  unsupported_claims_count: number;
  hallucination_warnings: string[];
  evidence_package: Array<{
    evidence_id: string;
    type: string;
    razorpay_field: string;
    source: string;
    reliability: number;
  }>;
}

export interface RequiredEvidence {
  type: string;
  description?: string;
  critical?: boolean;
  weight?: number;
}

export interface Policy {
  category: string;
  reason_code: string;
  network: string;
  reason_description: string;
  required_evidence: RequiredEvidence[];
}

export interface InvestigationResult {
  case_id: string;
  dispute_id: string;
  category: string;
  policy: Policy;
  evidence_graph: {
    nodes: EvidenceNode[];
    edges: Array<{ from: string; to: string; relation: string }>;
  };
  verification: {
    completeness_score: number;
    reliability_score: number;
    consistency_score: number;
    relevance_score: number;
    evidence_strength: string;
    available_evidence: string[];
    missing_critical: string[];
    missing_optional: string[];
    contradictions: string[];
    relevance_warnings: string[];
    summary_by_type: Record<string, string>;
  };
  decision: {
    recommendation: Recommendation;
    confidence: number;
    evidence_strength: string;
    reasoning: string;
    structured_explanation?: {
      key_findings: string[];
      missing_critical: string[];
      missing_optional: string[];
      contradictions: string[];
      safety_checks: Record<string, string>;
      downgraded_from?: string;
      downgrade_trigger?: string[];
      downgrade_quotes?: string[];
    };
  };
  rebuttal: Rebuttal;
  extraction?: ExtractionResult;
  audit_trail: Array<{ stage: string; action: string }>;
}

export type Recommendation = 'CONTEST' | 'REVIEW' | 'DO_NOT_CONTEST';

export interface SystemMode {
  mode: 'live' | 'simulated';
  simulated: boolean;
  key_id: string | null;
  base_url: string;
  reason: string;
}

export interface LLMMode {
  enabled: boolean;
  provider: string;
  model: string | null;
  base_url: string;
  reason: string;
}

export interface SubmissionState {
  ok: boolean;
  action: string;
  simulated?: boolean;
  message?: string;
  error?: string;
}

export type TabId = 'overview' | 'queue' | 'policy' | 'evaluation' | 'disputes' | 'benchmark';

export const DECISION_LABELS: Record<string, string> = {
  CONTEST: 'Recommend Contest',
  REVIEW: 'Human Review Required',
  DO_NOT_CONTEST: 'Accept / No Defensible Evidence',
};

export const CATEGORY_LABELS: Record<string, string> = {
  goods_not_received: 'Goods Not Received',
  credit_not_processed: 'Credit Not Processed',
  not_as_described: 'Not as Described',
  cancelled_merchandise: 'Cancelled Merchandise',
  unauthorized_fraud: 'Unauthorized / Fraud',
};

// ---------------------------------------------------------------------------
// Risk layer — served from ml/ artifacts (real held-out IEEE-CIS predictions).
// ---------------------------------------------------------------------------

export type RiskAction = 'APPROVE' | 'STEP_UP' | 'REVIEW' | 'BLOCK';

export interface RiskStatus {
  available: boolean;
  reason?: string;
  dataset?: string;
  rows_train?: number;
  rows_calib?: number;
  rows_test?: number;
  split?: string;
  fold_days?: number;
  fraud_rate_test?: number;
  pr_auc?: number;
  roc_auc?: number;
  usd_inr?: number;
}

export interface RiskSummary {
  available: boolean;
  transactions?: number;
  fold_days?: number;
  fraud_rate?: number;
  value_inr?: number;
  actions?: Record<string, number>;
  approved_fraud?: number;
  blocked_legit?: number;
  saving_per_1k_inr?: number;
  saving_pct?: number;
  best_baseline?: string;
}

export interface QueueItem {
  transaction_id: number;
  day: number;
  amount_inr: number;
  p_fraud: number;
  expected_loss_inr: number;
  action: RiskAction;
  is_fraud: number;
  segment: string | null;
  card_network: string | null;
  card_type: string | null;
  email_domain: string | null;
  device: string | null;
}

export interface QueuePage {
  total: number;
  offset: number;
  limit: number;
  items: QueueItem[];
}

export interface Segment {
  segment: string;
  transactions: number;
  disputes: number;
  approved_fraud: number;
  own_rate_bps: number;
  residual_rate_bps: number;
  portfolio_bps_contributed: number;
  value_inr: number;
}

export interface SegmentView {
  available: boolean;
  total_transactions?: number;
  total_disputes?: number;
  portfolio_bps?: number;
  segments: Segment[];
}

export interface OperatingPoint {
  name: string;
  threshold: number;
  precision: number;
  recall: number;
  flagged: number;
  flagged_rate: number;
  true_positives: number;
  false_positives: number;
}

export interface Evaluation {
  available: boolean;
  rows_test?: number;
  fraud_rate_test?: number;
  pr_auc?: number;
  roc_auc?: number;
  pr_auc_baseline?: number;
  lift?: number;
  brier_raw?: number;
  brier_calibrated?: number;
  operating_points?: OperatingPoint[];
  calibration_bins?: Array<{ bin: number; n: number; predicted: number; observed: number }>;
  top_features?: Array<{ feature: string; gain: number }>;
  train_seconds?: number;
}

export interface StrategyResult {
  name: string;
  total_cost_inr: number;
  cost_per_1k_inr: number;
  approved: number;
  stepped_up: number;
  reviewed: number;
  blocked: number;
  fraud_approved: number;
  legit_blocked: number;
  review_load: number;
}

export interface MoneyReport {
  available: boolean;
  strategies?: StrategyResult[];
  saving_per_1k_inr?: number;
  saving_pct?: number;
  best_baseline?: string;
  vamp_thresholds_verified?: boolean;
}

export interface PolicyBand {
  from: number;
  to: number;
  action: RiskAction;
}

export interface PolicySimulation {
  amount_inr: number;
  costs: Record<string, number>;
  applied_overrides: Record<string, number>;
  bands: PolicyBand[];
}

export const ACTION_LABELS: Record<RiskAction, string> = {
  APPROVE: 'Approve',
  STEP_UP: 'Step-up auth',
  REVIEW: 'Manual review',
  BLOCK: 'Block',
};

export interface ChartData {
  available: boolean;
  rows: number;
  fraud_rate: number;
  pr_auc?: number;
  median_ticket_inr: number;
  pr_curve: Array<{ recall: number; precision: number; threshold: number }>;
  distribution: {
    scale: string;
    bins: Array<{ from: number; to: number; legit: number; fraud: number }>;
  };
  cost_curve: {
    curve: Array<{ threshold: number; cost_per_1k: number }>;
    policy_cost_per_1k: number;
    approve_all_cost_per_1k: number;
    best_threshold: number;
    best_threshold_cost_per_1k: number;
  };
  sensitivity: {
    rows: Array<{ field: string; label: string; value: number; saving_pct: number; saving_per_1k_inr: number }>;
    wins: number;
    total: number;
  };
  policy_bands: PolicyBand[];
}
