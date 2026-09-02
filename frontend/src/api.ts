import type { DisputeSummary, InvestigationResult, LLMMode, SystemMode } from './types';

async function readJson(res: Response): Promise<any> {
  const text = await res.text();
  try {
    return text ? JSON.parse(text) : {};
  } catch {
    throw new Error(`Server returned non-JSON (${res.status}): ${text.slice(0, 160)}`);
  }
}

export async function fetchDisputes(): Promise<DisputeSummary[]> {
  const res = await fetch('/api/disputes');
  const data = await readJson(res);
  if (!res.ok) throw new Error(data.detail || `Failed to load disputes (${res.status})`);
  return data.disputes || [];
}

export async function fetchSystemMode(): Promise<{ razorpay: SystemMode | null; llm: LLMMode | null }> {
  const res = await fetch('/api/system/mode');
  const data = await readJson(res);
  if (!res.ok) throw new Error(data.detail || `Failed to read mode (${res.status})`);
  return { razorpay: data.razorpay || null, llm: data.llm || null };
}

export async function investigate(caseId: string): Promise<InvestigationResult> {
  const res = await fetch(`/api/disputes/${caseId}/investigate`, { method: 'POST' });
  const data = await readJson(res);
  if (!res.ok) throw new Error(data.detail || `Investigation failed (${res.status})`);
  return data;
}

export interface SubmitResponse {
  action: string;
  simulated: boolean;
  message: string;
}

export async function approveAndSubmit(
  caseId: string,
  action: 'CONTEST' | 'ACCEPT' | 'ESCALATE',
  reviewerNotes?: string,
): Promise<SubmitResponse> {
  const res = await fetch(`/api/disputes/${caseId}/approve-and-submit`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action, reviewer_notes: reviewerNotes }),
  });
  const data = await readJson(res);
  if (!res.ok) throw new Error(data.detail || `Request failed (${res.status})`);
  return {
    action: data.action || action,
    simulated: Boolean(data.simulated),
    message: data.message,
  };
}

// --- risk layer -------------------------------------------------------------
import type {
  ChartData,
  Evaluation,
  MoneyReport,
  PolicySimulation,
  QueuePage,
  RiskStatus,
  RiskSummary,
  SegmentView,
} from './types';

async function getJson<T>(url: string): Promise<T> {
  const res = await fetch(url);
  const data = await readJson(res);
  if (!res.ok) throw new Error(data.detail || `Request failed (${res.status})`);
  return data as T;
}

export const fetchRiskStatus = () => getJson<RiskStatus>('/api/risk/status');
export const fetchRiskSummary = () => getJson<RiskSummary>('/api/risk/summary');
export const fetchSegments = () => getJson<SegmentView>('/api/risk/segments');
export const fetchEvaluation = () => getJson<Evaluation>('/api/risk/evaluation');
export const fetchMoney = () => getJson<MoneyReport>('/api/risk/money');
export const fetchCharts = () => getJson<ChartData>('/api/risk/charts');
export const fetchPolicyDefaults = () => getJson<Record<string, number>>('/api/risk/policy/defaults');

export function fetchQueue(params: {
  limit?: number;
  offset?: number;
  action?: string;
  segment?: string;
  minProbability?: number;
}): Promise<QueuePage> {
  const q = new URLSearchParams();
  if (params.limit != null) q.set('limit', String(params.limit));
  if (params.offset != null) q.set('offset', String(params.offset));
  if (params.action) q.set('action', params.action);
  if (params.segment) q.set('segment', params.segment);
  if (params.minProbability) q.set('min_probability', String(params.minProbability));
  return getJson<QueuePage>(`/api/risk/queue?${q.toString()}`);
}

export async function simulatePolicy(
  amountInr: number,
  overrides: Record<string, number>,
): Promise<PolicySimulation> {
  const res = await fetch('/api/risk/policy/simulate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ amount_inr: amountInr, overrides }),
  });
  const data = await readJson(res);
  if (!res.ok) throw new Error(data.detail || `Simulation failed (${res.status})`);
  return data as PolicySimulation;
}
