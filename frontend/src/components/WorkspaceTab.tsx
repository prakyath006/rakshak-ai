import { Info, Search } from 'lucide-react';
import type { DisputeSummary, InvestigationResult, SubmissionState } from '../types';
import { CATEGORY_LABELS } from '../types';
import { Card } from './ui';
import CaseSummaryPanel from './workspace/CaseSummaryPanel';
import AuditTrailPanel from './workspace/AuditTrailPanel';
import EvidenceGraphPanel from './workspace/EvidenceGraphPanel';
import VerificationMatrixPanel from './workspace/VerificationMatrixPanel';
import DecisionPanel from './workspace/DecisionPanel';
import ExtractionPanel from './workspace/ExtractionPanel';
import RebuttalPanel from './workspace/RebuttalPanel';
import ApprovalGatePanel from './workspace/ApprovalGatePanel';
import InvestigationSkeleton from './workspace/InvestigationSkeleton';

export default function WorkspaceTab({
  disputes,
  investigation,
  loading,
  llmEnabled,
  error,
  selectedCaseId,
  onSelectCase,
  searchTerm,
  onSearchChange,
  filterCategory,
  onFilterChange,
  selectedNode,
  onSelectNode,
  highlightedEvidenceId,
  onCiteClick,
  submission,
  submitting,
  onSubmit,
  onResetSubmission,
}: {
  disputes: DisputeSummary[];
  investigation: InvestigationResult | null;
  loading: boolean;
  llmEnabled: boolean;
  error: string | null;
  selectedCaseId: string;
  onSelectCase: (id: string) => void;
  searchTerm: string;
  onSearchChange: (v: string) => void;
  filterCategory: string;
  onFilterChange: (v: string) => void;
  selectedNode: string | null;
  onSelectNode: (id: string | null) => void;
  highlightedEvidenceId: string | null;
  onCiteClick: (id: string) => void;
  submission: SubmissionState | null;
  submitting: boolean;
  onSubmit: (action: 'CONTEST' | 'ACCEPT' | 'ESCALATE', notes?: string) => void;
  onResetSubmission: () => void;
}) {
  const term = searchTerm.toLowerCase();
  const filtered = disputes.filter((d) => {
    const matchesCategory = filterCategory === 'all' || d.category === filterCategory;
    const matchesSearch =
      d.title.toLowerCase().includes(term) ||
      d.dispute_id.toLowerCase().includes(term) ||
      d.case_id.toLowerCase().includes(term) ||
      d.reason_code.includes(searchTerm);
    return matchesCategory && matchesSearch;
  });

  const dispute = disputes.find((d) => d.case_id === investigation?.case_id);

  const selected = disputes.find((d) => d.case_id === selectedCaseId);

  return (
    <div className="space-y-6">
      {/* These 20 cases are the only synthetic data left in the product — every
          other tab reads real held-out IEEE-CIS predictions. Saying so plainly
          matters more here than anywhere else, because a reader who assumes
          these are live disputes has misread the whole system. */}
      <div className="bg-warn/[.09] border border-warn/50 px-4 py-3 flex gap-3">
        <Info className="w-4 h-4 text-[#8a6110] shrink-0 mt-px" />
        <div className="note text-graphite-700 leading-relaxed">
          <strong className="text-graphite-900">
            These are 20 hand-written test cases, not live disputes.
          </strong>{' '}
          Disputes are raised by the issuing bank, so a merchant cannot create one through the API
          and the Razorpay test account has none. Each case is one scenario archetype with a known
          correct answer, used as the agent&rsquo;s regression suite — it is what caught the
          model misreading &ldquo;refund <em>has been</em> processed&rdquo; as a refund promise.
          Everything on the other four tabs is real held-out data.
        </div>
      </div>

      <Card className="p-4">
        <div className="flex flex-col lg:flex-row gap-4 lg:items-center lg:justify-between">
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
            <div className="relative sm:w-64">
              <Search className="w-4 h-4 text-graphite-500 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                placeholder="Search case, dispute ID, reason code…"
                value={searchTerm}
                onChange={(e) => onSearchChange(e.target.value)}
                aria-label="Search disputes"
                className="w-full bg-paper border border-paper-rule pl-9 pr-3 py-2 text-xs text-graphite-900 placeholder-graphite-400 focus:outline-none focus:border-press"
              />
            </div>

            <select
              value={filterCategory}
              onChange={(e) => onFilterChange(e.target.value)}
              aria-label="Filter by category"
              className="bg-paper border border-paper-rule px-3 py-2 text-xs text-graphite-700 focus:outline-none focus:border-press"
            >
              <option value="all">All categories ({disputes.length})</option>
              {Object.entries(CATEGORY_LABELS).map(([key, label]) => (
                <option key={key} value={key}>
                  {label}
                </option>
              ))}
            </select>
          </div>

          <span className="note shrink-0">
            {filtered.length} case{filtered.length === 1 ? '' : 's'}
          </span>
        </div>

        {/* A bare "GOLDEN-04" says nothing about what the case tests, so each
            button carries its scenario and the answer it is asserting. */}
        <div className="mt-4 pt-4 border-t border-paper-rule-soft grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-px bg-paper-rule">
          {filtered.length === 0 && (
            <span className="bg-paper-raised px-3 py-4 text-xs text-graphite-400">
              No matching cases
            </span>
          )}
          {filtered.map((d) => {
            const on = selectedCaseId === d.case_id;
            return (
              <button
                key={d.case_id}
                onClick={() => onSelectCase(d.case_id)}
                aria-pressed={on}
                title={d.title}
                className={`text-left px-3 py-2.5 transition-colors ${
                  on ? 'bg-press text-paper' : 'bg-paper-raised hover:bg-paper-sunk'
                }`}
              >
                <div className="flex items-baseline justify-between gap-2">
                  <span className={`fig text-[.65rem] ${on ? 'text-paper/70' : 'text-graphite-400'}`}>
                    {d.case_id}
                  </span>
                  <span
                    className={`fig text-[.6rem] uppercase tracking-[.06em] ${
                      on
                        ? 'text-paper/70'
                        : d.expected_decision === 'CONTEST'
                        ? 'text-gain'
                        : d.expected_decision === 'DO_NOT_CONTEST'
                        ? 'text-loss'
                        : 'text-[#8a6110]'
                    }`}
                  >
                    {d.expected_decision === 'DO_NOT_CONTEST' ? 'accept' : d.expected_decision.toLowerCase()}
                  </span>
                </div>
                <div className={`text-[.78rem] leading-snug mt-1 ${on ? 'text-paper' : 'text-graphite-700'}`}>
                  {d.title}
                </div>
              </button>
            );
          })}
        </div>
      </Card>

      {selected && (
        <p className="note -mt-3">
          Showing <span className="fig text-graphite-900">{selected.case_id}</span> — {selected.title}.
          Expected outcome:{' '}
          <span className="fig text-graphite-900">
            {selected.expected_decision === 'DO_NOT_CONTEST' ? 'accept' : selected.expected_decision.toLowerCase()}
          </span>
          .
        </p>
      )}

      {error && (
        <div className="bg-loss/[.08] border border-loss/35 p-4 text-xs text-loss">{error}</div>
      )}

      {loading && !investigation && <InvestigationSkeleton llmEnabled={llmEnabled} />}

      {investigation && (
        <div className={`grid grid-cols-1 lg:grid-cols-12 gap-4 xl:gap-6 ${loading ? 'opacity-60' : ''}`}>
          <div className="lg:col-span-3 space-y-4">
            <CaseSummaryPanel investigation={investigation} dispute={dispute} />
            <AuditTrailPanel investigation={investigation} submission={submission} />
          </div>

          <div className="lg:col-span-5 space-y-4">
            <EvidenceGraphPanel
              investigation={investigation}
              amount={dispute?.amount}
              selectedNode={selectedNode}
              onSelectNode={onSelectNode}
              highlightedEvidenceId={highlightedEvidenceId}
            />
            <VerificationMatrixPanel investigation={investigation} />
          </div>

          <div className="lg:col-span-4 space-y-4">
            <DecisionPanel investigation={investigation} />
            {investigation.extraction && <ExtractionPanel extraction={investigation.extraction} />}
            <RebuttalPanel rebuttal={investigation.rebuttal} onCiteClick={onCiteClick} />
            <ApprovalGatePanel
              investigation={investigation}
              submission={submission}
              submitting={submitting}
              onSubmit={onSubmit}
              onReset={onResetSubmission}
            />
          </div>
        </div>
      )}
    </div>
  );
}
