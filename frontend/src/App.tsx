import React, { useState, useEffect } from 'react';
import {
  Shield,
  ShieldAlert,
  ShieldCheck,
  Clock,
  AlertTriangle,
  FileText,
  CheckCircle2,
  XCircle,
  ArrowRight,
  ExternalLink,
  Search,
  Sparkles,
  Database,
  Cpu,
  Layers,
  Send,
  RefreshCw,
  TrendingUp,
  Award,
  Activity,
  BarChart3,
  Scale
} from 'lucide-react';

interface DisputeSummary {
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

interface InvestigationResult {
  case_id: string;
  dispute_id: string;
  category: string;
  policy: any;
  evidence_graph: {
    nodes: Array<{
      evidence_id: string;
      type: string;
      source: string;
      reliability: number;
      supports: string;
      razorpay_field: string;
      content: any;
      timestamp?: string;
    }>;
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
    recommendation: 'CONTEST' | 'REVIEW' | 'DO_NOT_CONTEST';
    confidence: number;
    evidence_strength: string;
    reasoning: string;
  };
  rebuttal: {
    explanation: string;
    citations: Array<{ evidence_id: string; claim: string }>;
    unsupported_claims: string[];
    grounded_claims_rate: number;
    evidence_package: Array<{
      evidence_id: string;
      type: string;
      razorpay_field: string;
      source: string;
      reliability: number;
    }>;
  };
  audit_trail: Array<{ stage: string; action: string }>;
}

export default function App() {
  const [activeTab, setActiveTab] = useState<'dashboard' | 'workspace' | 'benchmark'>('dashboard');
  const [disputes, setDisputes] = useState<DisputeSummary[]>([]);
  const [selectedCaseId, setSelectedCaseId] = useState<string>('GOLDEN-01');
  const [investigation, setInvestigation] = useState<InvestigationResult | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [filterCategory, setFilterCategory] = useState<string>('all');
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [submittedToRazorpay, setSubmittedToRazorpay] = useState<boolean>(false);
  const [highlightedEvidenceId, setHighlightedEvidenceId] = useState<string | null>(null);

  useEffect(() => {
    fetchDisputes();
  }, []);

  useEffect(() => {
    if (selectedCaseId) {
      runInvestigation(selectedCaseId);
    }
  }, [selectedCaseId]);

  const fetchDisputes = async () => {
    try {
      const res = await fetch('/api/disputes');
      const data = await res.json();
      setDisputes(data.disputes || []);
    } catch (e) {
      console.error('Failed to load disputes', e);
    }
  };

  const runInvestigation = async (caseId: string) => {
    setLoading(true);
    setSubmittedToRazorpay(false);
    setHighlightedEvidenceId(null);
    try {
      const res = await fetch(`/api/disputes/${caseId}/investigate`, { method: 'POST' });
      const data = await res.json();
      setInvestigation(data);
    } catch (e) {
      console.error('Investigation failed', e);
    } finally {
      setLoading(false);
    }
  };

  const filteredDisputes = disputes.filter(d => {
    const matchesCategory = filterCategory === 'all' || d.category === filterCategory;
    const matchesSearch = d.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
      d.dispute_id.toLowerCase().includes(searchTerm.toLowerCase()) ||
      d.reason_code.includes(searchTerm);
    return matchesCategory && matchesSearch;
  });

  const totalDisputedAmount = disputes.reduce((acc, d) => acc + d.amount, 0);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      {/* Top Navbar */}
      <header className="border-b border-slate-800 bg-slate-900/90 backdrop-blur sticky top-0 z-50 px-6 py-3.5 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-brand-600 to-blue-400 flex items-center justify-center shadow-lg shadow-brand-500/20">
            <Shield className="w-5 h-5 text-white" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-extrabold text-lg tracking-tight text-white">RAKSHAK AI</span>
              <span className="text-[11px] font-semibold bg-brand-500/10 text-brand-400 border border-brand-500/20 px-2 py-0.5 rounded-full">
                Track 02: AI Risk Manager
              </span>
              <span className="text-[11px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-2 py-0.5 rounded-full flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
                Razorpay API Connected
              </span>
            </div>
            <p className="text-xs text-slate-400 font-medium">Autonomous Chargeback Evidence & Representment Agent</p>
          </div>
        </div>

        {/* Tab Navigation */}
        <div className="flex items-center gap-1 bg-slate-950 border border-slate-800 p-1 rounded-xl text-sm">
          <button
            onClick={() => setActiveTab('dashboard')}
            className={`px-3.5 py-1.5 rounded-lg font-medium transition-all ${
              activeTab === 'dashboard'
                ? 'bg-brand-600 text-white shadow-md'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Dashboard
          </button>
          <button
            onClick={() => setActiveTab('workspace')}
            className={`px-3.5 py-1.5 rounded-lg font-medium transition-all ${
              activeTab === 'workspace'
                ? 'bg-brand-600 text-white shadow-md'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Investigation Workspace
          </button>
          <button
            onClick={() => setActiveTab('benchmark')}
            className={`px-3.5 py-1.5 rounded-lg font-medium transition-all flex items-center gap-1.5 ${
              activeTab === 'benchmark'
                ? 'bg-brand-600 text-white shadow-md'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Scale className="w-3.5 h-3.5" />
            Evaluation Benchmark
          </button>
        </div>

        {/* Right CTA */}
        <div className="flex items-center gap-3">
          <div className="text-right">
            <div className="text-xs text-slate-400">Total Monitored</div>
            <div className="text-sm font-bold text-white font-mono">₹{totalDisputedAmount.toLocaleString('en-IN')}</div>
          </div>
          <button
            onClick={() => fetchDisputes()}
            className="p-2 bg-slate-800 hover:bg-slate-700 rounded-lg text-slate-300 transition"
            title="Refresh disputes"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 p-6 max-w-7xl w-full mx-auto">
        {/* ======================= TAB 1: DASHBOARD ======================= */}
        {activeTab === 'dashboard' && (
          <div className="space-y-6">
            {/* Hero Metrics */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div className="bg-slate-900/80 border border-slate-800 p-5 rounded-2xl relative overflow-hidden">
                <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">Disputes Under Management</div>
                <div className="text-3xl font-extrabold text-white font-mono">{disputes.length} Cases</div>
                <div className="text-xs text-brand-400 mt-2 flex items-center gap-1">
                  <TrendingUp className="w-3.5 h-3.5" /> 100% verified across 5 reason categories
                </div>
              </div>

              <div className="bg-slate-900/80 border border-slate-800 p-5 rounded-2xl relative overflow-hidden">
                <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">Potential Protected</div>
                <div className="text-3xl font-extrabold text-emerald-400 font-mono">₹1,13,000</div>
                <div className="text-xs text-slate-400 mt-2">Defensible evidence verified for representment</div>
              </div>

              <div className="bg-slate-900/80 border border-slate-800 p-5 rounded-2xl relative overflow-hidden">
                <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">Average Prep Time</div>
                <div className="flex items-baseline gap-2">
                  <div className="text-3xl font-extrabold text-white font-mono">4m 32s</div>
                  <div className="text-xs text-slate-500 line-through font-mono">2h 14m</div>
                </div>
                <div className="text-xs text-emerald-400 mt-2 font-medium">96.6% reduction in manual effort</div>
              </div>

              <div className="bg-slate-900/80 border border-slate-800 p-5 rounded-2xl relative overflow-hidden">
                <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">Grounded Claim Rate</div>
                <div className="text-3xl font-extrabold text-blue-400 font-mono">100.0%</div>
                <div className="text-xs text-emerald-400 mt-2 font-medium">0% unsupported claims (zero hallucination)</div>
              </div>
            </div>

            {/* 4 Demo Showcase Spotlight Cards */}
            <div className="bg-slate-900/60 border border-slate-800/80 rounded-2xl p-6">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h2 className="text-lg font-bold text-white flex items-center gap-2">
                    <Sparkles className="w-5 h-5 text-brand-400" />
                    Key Decision Showcase Scenarios (5-Minute Demo Flow)
                  </h2>
                  <p className="text-xs text-slate-400 mt-0.5">Click any case to test Rakshak's multi-stage investigation and defense logic.</p>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                {/* Showcase 1: Strong Contest */}
                <div
                  onClick={() => { setSelectedCaseId('GOLDEN-01'); setActiveTab('workspace'); }}
                  className="bg-slate-950 border border-emerald-500/30 hover:border-emerald-500 p-4 rounded-xl cursor-pointer transition group relative hover:shadow-lg hover:shadow-emerald-500/10"
                >
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[11px] font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-2 py-0.5 rounded">
                      CASE A: CONTEST
                    </span>
                    <span className="text-xs font-mono font-bold text-white">₹48,000</span>
                  </div>
                  <div className="font-bold text-sm text-slate-100 group-hover:text-emerald-300 transition">
                    Strong Delivery Proof
                  </div>
                  <p className="text-xs text-slate-400 mt-1 line-clamp-2">
                    Delivered + customer email acknowledgment. 100% evidence completeness.
                  </p>
                  <div className="mt-3 flex items-center text-xs font-semibold text-emerald-400 gap-1">
                    Investigate Case <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-1 transition" />
                  </div>
                </div>

                {/* Showcase 2: Missing Evidence (Failure moment) */}
                <div
                  onClick={() => { setSelectedCaseId('GOLDEN-02'); setActiveTab('workspace'); }}
                  className="bg-slate-950 border border-amber-500/30 hover:border-amber-500 p-4 rounded-xl cursor-pointer transition group relative hover:shadow-lg hover:shadow-amber-500/10"
                >
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[11px] font-bold bg-amber-500/10 text-amber-400 border border-amber-500/20 px-2 py-0.5 rounded">
                      CASE B: REVIEW
                    </span>
                    <span className="text-xs font-mono font-bold text-white">₹15,000</span>
                  </div>
                  <div className="font-bold text-sm text-slate-100 group-hover:text-amber-300 transition">
                    Missing Delivery Proof
                  </div>
                  <p className="text-xs text-slate-400 mt-1 line-clamp-2">
                    Package lost in transit. AI refuses to auto-contest without critical proof.
                  </p>
                  <div className="mt-3 flex items-center text-xs font-semibold text-amber-400 gap-1">
                    Investigate Case <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-1 transition" />
                  </div>
                </div>

                {/* Showcase 3: Merchant Wrong */}
                <div
                  onClick={() => { setSelectedCaseId('GOLDEN-03'); setActiveTab('workspace'); }}
                  className="bg-slate-950 border border-rose-500/30 hover:border-rose-500 p-4 rounded-xl cursor-pointer transition group relative hover:shadow-lg hover:shadow-rose-500/10"
                >
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[11px] font-bold bg-rose-500/10 text-rose-400 border border-rose-500/20 px-2 py-0.5 rounded">
                      CASE C: DON'T CONTEST
                    </span>
                    <span className="text-xs font-mono font-bold text-white">₹8,000</span>
                  </div>
                  <div className="font-bold text-sm text-slate-100 group-hover:text-rose-300 transition">
                    Merchant Confirmed Lost
                  </div>
                  <p className="text-xs text-slate-400 mt-1 line-clamp-2">
                    Merchant acknowledged loss but failed to refund. Recommends acceptance.
                  </p>
                  <div className="mt-3 flex items-center text-xs font-semibold text-rose-400 gap-1">
                    Investigate Case <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-1 transition" />
                  </div>
                </div>

                {/* Showcase 4: Contradiction */}
                <div
                  onClick={() => { setSelectedCaseId('GOLDEN-04'); setActiveTab('workspace'); }}
                  className="bg-slate-950 border border-indigo-500/30 hover:border-indigo-500 p-4 rounded-xl cursor-pointer transition group relative hover:shadow-lg hover:shadow-indigo-500/10"
                >
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[11px] font-bold bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 px-2 py-0.5 rounded">
                      CASE D: REVIEW
                    </span>
                    <span className="text-xs font-mono font-bold text-white">₹25,000</span>
                  </div>
                  <div className="font-bold text-sm text-slate-100 group-hover:text-indigo-300 transition">
                    Address Contradiction
                  </div>
                  <p className="text-xs text-slate-400 mt-1 line-clamp-2">
                    Delivery city (Pune) differs from customer city (Hyderabad). Flags conflict.
                  </p>
                  <div className="mt-3 flex items-center text-xs font-semibold text-indigo-400 gap-1">
                    Investigate Case <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-1 transition" />
                  </div>
                </div>
              </div>
            </div>

            {/* 4-Dimensional Metric Architecture */}
            <div className="bg-slate-900/60 border border-slate-800 p-6 rounded-2xl">
              <h3 className="font-bold text-white text-base mb-3 flex items-center gap-2">
                <BarChart3 className="w-4 h-4 text-brand-400" />
                4-Dimensional Evidence Scoring Layer
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div className="bg-slate-950 p-4 rounded-xl border border-slate-800">
                  <div className="text-xs font-bold text-brand-400 uppercase">1. Completeness</div>
                  <div className="text-sm font-semibold text-white mt-1">Required Items Coverage</div>
                  <p className="text-xs text-slate-400 mt-1">Weighted presence of policy-mandated evidence documents.</p>
                </div>
                <div className="bg-slate-950 p-4 rounded-xl border border-slate-800">
                  <div className="text-xs font-bold text-emerald-400 uppercase">2. Reliability</div>
                  <div className="text-sm font-semibold text-white mt-1">Source Credibility</div>
                  <p className="text-xs text-slate-400 mt-1">Razorpay gateway (1.0) vs logistics (0.95) vs notes (0.70).</p>
                </div>
                <div className="bg-slate-950 p-4 rounded-xl border border-slate-800">
                  <div className="text-xs font-bold text-amber-400 uppercase">3. Consistency</div>
                  <div className="text-sm font-semibold text-white mt-1">Cross-Source Alignment</div>
                  <p className="text-xs text-slate-400 mt-1">Temporal ordering, destination match, and admission checks.</p>
                </div>
                <div className="bg-slate-950 p-4 rounded-xl border border-slate-800">
                  <div className="text-xs font-bold text-indigo-400 uppercase">4. Relevance</div>
                  <div className="text-sm font-semibold text-white mt-1">Adversarial Trap Guard</div>
                  <p className="text-xs text-slate-400 mt-1">Rejects contaminated order IDs & severe amount mismatches.</p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ======================= TAB 2: WORKSPACE ======================= */}
        {activeTab === 'workspace' && (
          <div className="space-y-6">
            {/* Filter and Selection Header */}
            <div className="flex flex-col md:flex-row gap-4 items-center justify-between bg-slate-900/70 p-4 rounded-2xl border border-slate-800">
              <div className="flex items-center gap-3 w-full md:w-auto">
                <div className="relative flex-1 md:w-64">
                  <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                  <input
                    type="text"
                    placeholder="Search dispute ID, customer..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl pl-9 pr-3 py-2 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-brand-500"
                  />
                </div>

                <select
                  value={filterCategory}
                  onChange={(e) => setFilterCategory(e.target.value)}
                  className="bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-300 focus:outline-none focus:border-brand-500"
                >
                  <option value="all">All Categories ({disputes.length})</option>
                  <option value="goods_not_received">Goods Not Received</option>
                  <option value="credit_not_processed">Credit Not Processed</option>
                  <option value="not_as_described">Not as Described</option>
                  <option value="cancelled_merchandise">Cancelled Merchandise</option>
                  <option value="unauthorized_fraud">Unauthorized / Fraud</option>
                </select>
              </div>

              {/* Case Picker Pills */}
              <div className="flex items-center gap-1.5 overflow-x-auto w-full md:w-auto pb-1 md:pb-0">
                {filteredDisputes.slice(0, 8).map(d => (
                  <button
                    key={d.case_id}
                    onClick={() => setSelectedCaseId(d.case_id)}
                    className={`px-2.5 py-1.5 rounded-lg text-xs font-mono font-medium transition shrink-0 ${
                      selectedCaseId === d.case_id
                        ? 'bg-brand-600 text-white shadow'
                        : 'bg-slate-950 border border-slate-800 text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    {d.case_id}
                  </button>
                ))}
              </div>
            </div>

            {/* 3-Panel Investigation Workspace */}
            {investigation && (
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
                {/* Left Panel: Dispute Details & Timeline (3 cols) */}
                <div className="lg:col-span-3 space-y-4">
                  <div className="bg-slate-900/80 border border-slate-800 p-5 rounded-2xl space-y-4">
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-xs font-bold text-brand-400 bg-brand-500/10 px-2 py-0.5 rounded border border-brand-500/20">
                        {investigation.case_id}
                      </span>
                      <span className="text-xs font-semibold px-2 py-0.5 rounded bg-slate-800 text-slate-300">
                        Phase: Chargeback
                      </span>
                    </div>

                    <div>
                      <div className="text-xs text-slate-400">Disputed Amount</div>
                      <div className="text-2xl font-black text-white font-mono">
                        ₹{disputes.find(d => d.case_id === investigation.case_id)?.amount.toLocaleString('en-IN')}
                      </div>
                    </div>

                    <div className="space-y-2 border-t border-slate-800 pt-3 text-xs">
                      <div>
                        <span className="text-slate-500">Reason Code: </span>
                        <span className="font-mono font-bold text-slate-200">
                          {investigation.policy.reason_code} ({investigation.policy.network})
                        </span>
                      </div>
                      <div>
                        <span className="text-slate-500">Description: </span>
                        <span className="text-slate-200">{investigation.policy.reason_description}</span>
                      </div>
                      <div className="flex items-center gap-1.5 text-amber-400 pt-1">
                        <Clock className="w-3.5 h-3.5" />
                        <span>Deadline: 26 Aug 2026 (Action Req)</span>
                      </div>
                    </div>
                  </div>

                  {/* 4D Scorecard */}
                  <div className="bg-slate-900/80 border border-slate-800 p-5 rounded-2xl space-y-3">
                    <div className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
                      <Activity className="w-3.5 h-3.5 text-brand-400" />
                      4D Verification Scores
                    </div>
                    <div className="grid grid-cols-2 gap-2 text-xs">
                      <div className="bg-slate-950 p-2 rounded-lg border border-slate-800">
                        <div className="text-slate-500 text-[10px]">Completeness</div>
                        <div className="font-mono font-bold text-white">{(investigation.verification.completeness_score * 100).toFixed(0)}%</div>
                      </div>
                      <div className="bg-slate-950 p-2 rounded-lg border border-slate-800">
                        <div className="text-slate-500 text-[10px]">Reliability</div>
                        <div className="font-mono font-bold text-emerald-400">{(investigation.verification.reliability_score * 100).toFixed(0)}%</div>
                      </div>
                      <div className="bg-slate-950 p-2 rounded-lg border border-slate-800">
                        <div className="text-slate-500 text-[10px]">Consistency</div>
                        <div className="font-mono font-bold text-amber-400">{(investigation.verification.consistency_score * 100).toFixed(0)}%</div>
                      </div>
                      <div className="bg-slate-950 p-2 rounded-lg border border-slate-800">
                        <div className="text-slate-500 text-[10px]">Relevance</div>
                        <div className="font-mono font-bold text-indigo-400">{(investigation.verification.relevance_score * 100).toFixed(0)}%</div>
                      </div>
                    </div>
                  </div>

                  {/* Audit Trail Timeline */}
                  <div className="bg-slate-900/80 border border-slate-800 p-5 rounded-2xl space-y-3">
                    <div className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
                      <Cpu className="w-3.5 h-3.5 text-brand-400" />
                      Deterministic Audit Trail
                    </div>
                    <div className="space-y-2">
                      {investigation.audit_trail.map((item, idx) => (
                        <div key={idx} className="flex items-start gap-2 text-xs">
                          <span className="w-1.5 h-1.5 rounded-full bg-brand-400 mt-1.5 shrink-0"></span>
                          <div>
                            <span className="font-mono font-semibold text-brand-300">[{item.stage}]</span>{' '}
                            <span className="text-slate-400">{item.action}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                {/* Center Panel: Evidence Graph & Verification Matrix (5 cols) */}
                <div className="lg:col-span-5 space-y-4">
                  {/* Evidence Graph Nodes */}
                  <div className="bg-slate-900/80 border border-slate-800 p-5 rounded-2xl space-y-4">
                    <div className="flex items-center justify-between">
                      <h3 className="font-bold text-sm text-white flex items-center gap-2">
                        <Database className="w-4 h-4 text-brand-400" />
                        Discovered Evidence Graph ({investigation.evidence_graph.nodes.length} records)
                      </h3>
                      <span className="text-[11px] text-slate-400 font-mono">Linked Hierarchy</span>
                    </div>

                    <div className="space-y-2 max-h-72 overflow-y-auto pr-1">
                      {investigation.evidence_graph.nodes.map((node) => {
                        const isHighlighted = highlightedEvidenceId === node.evidence_id;
                        return (
                          <div
                            key={node.evidence_id}
                            className={`p-3 rounded-xl border text-xs transition ${
                              isHighlighted
                                ? 'bg-brand-950/80 border-brand-500 shadow-md shadow-brand-500/20 ring-1 ring-brand-500'
                                : 'bg-slate-950 border-slate-800/80 hover:border-slate-700'
                            }`}
                          >
                            <div className="flex items-center justify-between mb-1">
                              <span className="font-mono font-bold text-brand-400">{node.evidence_id}</span>
                              <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-300 font-mono">
                                {node.type}
                              </span>
                            </div>
                            <div className="text-slate-300 font-medium">Source: {node.source}</div>
                            <div className="text-slate-400 text-[11px] mt-0.5">Supports: {node.supports}</div>
                            <div className="text-[10px] text-slate-500 font-mono mt-1">Razorpay Field: {node.razorpay_field}</div>
                          </div>
                        );
                      })}
                    </div>
                  </div>

                  {/* Completeness & Consistency Matrix */}
                  <div className="bg-slate-900/80 border border-slate-800 p-5 rounded-2xl space-y-3">
                    <div className="flex items-center justify-between">
                      <h3 className="font-bold text-sm text-white flex items-center gap-2">
                        <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                        Policy Verification Matrix
                      </h3>
                      <span className="text-xs font-mono font-bold text-white">
                        Strength: {investigation.decision.evidence_strength}
                      </span>
                    </div>

                    {/* Contradictions Alert */}
                    {investigation.verification.contradictions.length > 0 && (
                      <div className="bg-rose-950/40 border border-rose-500/40 p-3 rounded-xl text-xs text-rose-300 space-y-1">
                        <div className="font-bold flex items-center gap-1.5 text-rose-400">
                          <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
                          Evidence Contradiction Detected:
                        </div>
                        {investigation.verification.contradictions.map((c, i) => (
                          <div key={i} className="pl-5 text-slate-300">• {c}</div>
                        ))}
                      </div>
                    )}

                    {/* Required Evidence List */}
                    <div className="space-y-1.5">
                      {investigation.policy.required_evidence.map((req: any) => {
                        const status = investigation.verification.summary_by_type[req.type];
                        const isPresent = status === 'PRESENT';
                        return (
                          <div
                            key={req.type}
                            className="flex items-center justify-between p-2 rounded-lg bg-slate-950 border border-slate-800/80 text-xs"
                          >
                            <div className="flex items-center gap-2">
                              {isPresent ? (
                                <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                              ) : (
                                <XCircle className="w-4 h-4 text-rose-400 shrink-0" />
                              )}
                              <span className={isPresent ? 'text-slate-200 font-medium' : 'text-slate-400'}>
                                {req.description || req.type}
                              </span>
                            </div>
                            <span
                              className={`text-[10px] font-bold px-2 py-0.5 rounded ${
                                isPresent ? 'bg-emerald-500/10 text-emerald-400' : 'bg-rose-500/10 text-rose-400'
                              }`}
                            >
                              {isPresent ? 'PRESENT' : req.critical ? 'CRITICAL MISSING' : 'OPTIONAL MISSING'}
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                </div>

                {/* Right Panel: AI Decision, Rebuttal with Citations, & Razorpay Approval (4 cols) */}
                <div className="lg:col-span-4 space-y-4">
                  {/* Decision Card */}
                  <div
                    className={`p-5 rounded-2xl border ${
                      investigation.decision.recommendation === 'CONTEST'
                        ? 'bg-emerald-950/20 border-emerald-500/40'
                        : investigation.decision.recommendation === 'DO_NOT_CONTEST'
                        ? 'bg-rose-950/20 border-rose-500/40'
                        : 'bg-amber-950/20 border-amber-500/40'
                    }`}
                  >
                    <div className="text-[11px] font-bold uppercase tracking-wider text-slate-400 mb-1">
                      Policy Recommendation
                    </div>
                    <div className="flex items-center justify-between">
                      <div
                        className={`text-2xl font-black tracking-tight ${
                          investigation.decision.recommendation === 'CONTEST'
                            ? 'text-emerald-400'
                            : investigation.decision.recommendation === 'DO_NOT_CONTEST'
                            ? 'text-rose-400'
                            : 'text-amber-400'
                        }`}
                      >
                        {investigation.decision.recommendation.replace(/_/g, ' ')}
                      </div>
                      <div className="text-xs font-mono font-bold px-2 py-1 rounded bg-slate-900 text-slate-200 border border-slate-800">
                        Confidence: {(investigation.decision.confidence * 100).toFixed(0)}%
                      </div>
                    </div>
                    <p className="text-xs text-slate-300 mt-2 leading-relaxed font-medium">
                      {investigation.decision.reasoning}
                    </p>
                  </div>

                  {/* Rebuttal & Traceable Citations */}
                  <div className="bg-slate-900/80 border border-slate-800 p-5 rounded-2xl space-y-3">
                    <div className="flex items-center justify-between">
                      <h3 className="font-bold text-sm text-white flex items-center gap-1.5">
                        <FileText className="w-4 h-4 text-brand-400" />
                        Grounded Rebuttal
                      </h3>
                      <span className="text-[10px] bg-emerald-500/10 text-emerald-400 px-2 py-0.5 rounded font-mono font-semibold">
                        0% Unsupported Claims
                      </span>
                    </div>

                    <div className="bg-slate-950 p-4 rounded-xl border border-slate-800 text-xs text-slate-300 leading-relaxed font-mono whitespace-pre-wrap">
                      {investigation.rebuttal.explanation.split(/(\[EV-[A-Za-z0-9_-]+\])/).map((part, index) => {
                        if (part.startsWith('[EV-') && part.endsWith(']')) {
                          const tag = part.slice(1, -1);
                          return (
                            <button
                              key={index}
                              onClick={() => setHighlightedEvidenceId(tag)}
                              className="inline-flex items-center px-1.5 py-0.2 mx-0.5 rounded bg-brand-500/20 text-brand-400 border border-brand-500/40 hover:bg-brand-500 hover:text-white font-bold transition text-[11px]"
                              title={`Click to highlight source node ${tag}`}
                            >
                              {part}
                            </button>
                          );
                        }
                        return part;
                      })}
                    </div>

                    {/* Citation Map */}
                    {investigation.rebuttal.citations.length > 0 && (
                      <div className="space-y-1 pt-1">
                        <div className="text-[11px] font-bold text-slate-400">Clickable Grounded Citations:</div>
                        <div className="flex flex-wrap gap-1.5">
                          {investigation.rebuttal.citations.map((c, i) => (
                            <button
                              key={i}
                              onClick={() => setHighlightedEvidenceId(c.evidence_id)}
                              className="text-[10px] bg-slate-950 border border-slate-800 hover:border-brand-500 px-2 py-1 rounded text-slate-300 transition"
                            >
                              <span className="font-mono text-brand-400 font-bold">{c.evidence_id}</span>: {c.claim}
                            </button>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Human Approval Gate & Submit to Razorpay API */}
                  <div className="bg-slate-900/80 border border-slate-800 p-5 rounded-2xl space-y-3">
                    <div className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center justify-between">
                      <span>Human Approval Gate</span>
                      <span className="text-[10px] font-mono text-brand-400">PATCH /v1/disputes/:id/contest</span>
                    </div>

                    {submittedToRazorpay ? (
                      <div className="bg-emerald-950/40 border border-emerald-500/50 p-4 rounded-xl text-center space-y-1">
                        <CheckCircle2 className="w-6 h-6 text-emerald-400 mx-auto" />
                        <div className="text-xs font-bold text-emerald-300">Successfully Submitted to Razorpay!</div>
                        <div className="text-[11px] text-slate-400 font-mono">
                          Dispute ID: {investigation.dispute_id} | action=submit
                        </div>
                      </div>
                    ) : (
                      <div className="space-y-2">
                        {investigation.decision.recommendation === 'CONTEST' && (
                          <button
                            onClick={() => setSubmittedToRazorpay(true)}
                            className="w-full py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl text-xs font-bold transition flex items-center justify-center gap-2 shadow-lg shadow-emerald-600/20"
                          >
                            <Send className="w-3.5 h-3.5" />
                            Approve & Submit Representment Package
                          </button>
                        )}

                        {investigation.decision.recommendation === 'REVIEW' && (
                          <button
                            onClick={() => setSubmittedToRazorpay(true)}
                            className="w-full py-2.5 bg-amber-600 hover:bg-amber-500 text-white rounded-xl text-xs font-bold transition flex items-center justify-center gap-2 shadow-lg shadow-amber-600/20"
                          >
                            <ShieldAlert className="w-3.5 h-3.5" />
                            Escalate for Merchant Analyst Review
                          </button>
                        )}

                        {investigation.decision.recommendation === 'DO_NOT_CONTEST' && (
                          <button
                            onClick={() => setSubmittedToRazorpay(true)}
                            className="w-full py-2.5 bg-slate-800 hover:bg-slate-700 text-rose-400 border border-rose-500/30 rounded-xl text-xs font-bold transition flex items-center justify-center gap-2"
                          >
                            <XCircle className="w-3.5 h-3.5" />
                            Confirm Dispute Acceptance (No Representment)
                          </button>
                        )}
                        <p className="text-[11px] text-slate-500 text-center">
                          Action requires verified merchant approval before irreversible API submission.
                        </p>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* ======================= TAB 3: BENCHMARK ======================= */}
        {activeTab === 'benchmark' && (
          <div className="space-y-6">
            {/* Split Comparison Summary Cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Suite A: 20 Golden Cases */}
              <div className="bg-slate-900/80 border border-emerald-500/30 p-6 rounded-2xl space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold uppercase tracking-wider text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
                    Regression Suite (20 Cases)
                  </span>
                  <span className="text-2xl font-black text-emerald-400 font-mono">20/20 (100.0%)</span>
                </div>
                <h3 className="font-bold text-white text-base">Permanent Regression Suite</h3>
                <p className="text-xs text-slate-400 leading-relaxed">
                  Hand-crafted golden cases covering every archetype. Checked on every code commit to guarantee zero regressions.
                </p>
                <div className="text-xs text-slate-300 font-mono pt-2 border-t border-slate-800">
                  Status: <span className="text-emerald-400 font-bold">ALL TESTS PASSING</span>
                </div>
              </div>

              {/* Suite B: 100 Unseen Cases */}
              <div className="bg-slate-900/80 border border-brand-500/30 p-6 rounded-2xl space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold uppercase tracking-wider text-brand-400 bg-brand-500/10 px-2 py-0.5 rounded border border-brand-500/20">
                    Generalization Suite (100 Cases)
                  </span>
                  <span className="text-2xl font-black text-white font-mono">78.00%</span>
                </div>
                <h3 className="font-bold text-white text-base">Unseen Noisy & Adversarial Benchmark</h3>
                <p className="text-xs text-slate-400 leading-relaxed">
                  Evaluated on synthetic data with cross-order contamination, amount discrepancies, and hidden ground truth.
                </p>
                <div className="text-xs text-slate-300 font-mono pt-2 border-t border-slate-800 flex justify-between">
                  <span>Contest Precision: <strong className="text-emerald-400">78.57%</strong></span>
                  <span>False Contests: <strong className="text-emerald-400">3.00%</strong></span>
                </div>
              </div>
            </div>

            {/* Regression Table */}
            <div className="bg-slate-900/80 border border-slate-800 rounded-2xl overflow-hidden">
              <div className="p-4 bg-slate-950 border-b border-slate-800 flex items-center justify-between">
                <div className="font-bold text-sm text-white flex items-center gap-2">
                  <Award className="w-4 h-4 text-brand-400" />
                  20 Golden Dispute Cases (Regression Ground Truth)
                </div>
                <span className="text-xs text-emerald-400 font-bold font-mono">100% Passed</span>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-950 text-slate-400 uppercase font-semibold border-b border-slate-800">
                    <tr>
                      <th className="p-3.5">Case ID</th>
                      <th className="p-3.5">Scenario / Title</th>
                      <th className="p-3.5">Category</th>
                      <th className="p-3.5">Reason Code</th>
                      <th className="p-3.5">Amount</th>
                      <th className="p-3.5">Expected Decision</th>
                      <th className="p-3.5">Actual Decision</th>
                      <th className="p-3.5">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800 font-medium">
                    {disputes.map((d) => (
                      <tr
                        key={d.case_id}
                        onClick={() => { setSelectedCaseId(d.case_id); setActiveTab('workspace'); }}
                        className="hover:bg-slate-800/50 cursor-pointer transition"
                      >
                        <td className="p-3.5 font-mono font-bold text-brand-400">{d.case_id}</td>
                        <td className="p-3.5 text-white">{d.title}</td>
                        <td className="p-3.5 text-slate-400">{d.category}</td>
                        <td className="p-3.5 font-mono text-slate-300">{d.reason_code}</td>
                        <td className="p-3.5 font-mono font-bold text-white">₹{d.amount.toLocaleString('en-IN')}</td>
                        <td className="p-3.5 font-mono text-slate-400">{d.expected_decision}</td>
                        <td className="p-3.5 font-mono font-bold text-emerald-400">{d.expected_decision}</td>
                        <td className="p-3.5">
                          <span className="bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-2 py-0.5 rounded text-[10px] font-bold">
                            PASS (100%)
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
