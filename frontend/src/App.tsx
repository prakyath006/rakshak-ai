import { useCallback, useEffect, useState } from 'react';
import * as api from './api';
import type {
  DisputeSummary,
  InvestigationResult,
  LLMMode,
  SubmissionState,
  SystemMode,
  TabId,
} from './types';
import Header from './components/Header';
import WorkspaceTab from './components/WorkspaceTab';
import OverviewTab from './components/risk/OverviewTab';
import QueueTab from './components/risk/QueueTab';
import PolicyTab from './components/risk/PolicyTab';
import EvaluationTab from './components/risk/EvaluationTab';

export default function App({ onExit }: { onExit?: () => void }) {
  const [activeTab, setActiveTab] = useState<TabId>('overview');
  const [queueAction, setQueueAction] = useState<string | undefined>();
  const [disputes, setDisputes] = useState<DisputeSummary[]>([]);
  const [selectedCaseId, setSelectedCaseId] = useState<string>('GOLDEN-01');
  const [investigation, setInvestigation] = useState<InvestigationResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [filterCategory, setFilterCategory] = useState('all');
  const [searchTerm, setSearchTerm] = useState('');
  const [highlightedEvidenceId, setHighlightedEvidenceId] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<string | null>(null);

  const [systemMode, setSystemMode] = useState<SystemMode | null>(null);
  const [llmMode, setLlmMode] = useState<LLMMode | null>(null);
  const [submission, setSubmission] = useState<SubmissionState | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const loadDisputes = useCallback(async () => {
    try {
      setDisputes(await api.fetchDisputes());
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load disputes');
    }
  }, []);

  const loadSystemMode = useCallback(async () => {
    try {
      const { razorpay, llm } = await api.fetchSystemMode();
      setSystemMode(razorpay);
      setLlmMode(llm);
    } catch {
      // A missing mode reads as "unknown" in the header rather than a hard failure —
      // the rest of the app is still usable.
      setSystemMode(null);
      setLlmMode(null);
    }
  }, []);

  useEffect(() => {
    loadDisputes();
    loadSystemMode();
  }, [loadDisputes, loadSystemMode]);

  useEffect(() => {
    if (!selectedCaseId) return;
    let cancelled = false;

    (async () => {
      setLoading(true);
      setError(null);
      setSubmission(null);
      setHighlightedEvidenceId(null);
      setSelectedNode(null);
      try {
        const result = await api.investigate(selectedCaseId);
        if (!cancelled) setInvestigation(result);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Investigation failed');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    // Guards against a slow response for a previously-selected case landing after
    // the user has already moved on to another one.
    return () => {
      cancelled = true;
    };
  }, [selectedCaseId]);

  const submitDecision = async (action: 'CONTEST' | 'ACCEPT' | 'ESCALATE', notes?: string) => {
    if (!investigation) return;
    setSubmitting(true);
    try {
      const res = await api.approveAndSubmit(investigation.case_id, action, notes);
      setSubmission({ ok: true, action: res.action, simulated: res.simulated, message: res.message });
    } catch (e) {
      setSubmission({ ok: false, action, error: e instanceof Error ? e.message : 'Network error' });
    } finally {
      setSubmitting(false);
    }
  };

  const openCase = (caseId: string) => {
    setSelectedCaseId(caseId);
    setActiveTab('disputes');
  };

  const citeEvidence = (evidenceId: string) => {
    setHighlightedEvidenceId(evidenceId);
    setSelectedNode(evidenceId);
  };

  return (
    <div className="doc min-h-screen font-sans antialiased flex flex-col">
      <Header
        activeTab={activeTab}
        onTabChange={setActiveTab}
        systemMode={systemMode}
        llmMode={llmMode}
        onExit={onExit}
        onRefresh={() => {
          loadDisputes();
          loadSystemMode();
        }}
      />

      <main className="flex-1 px-5 sm:px-7 py-7 max-w-[104rem] w-full mx-auto">
        {activeTab === 'overview' && (
          <OverviewTab
            onOpenQueue={(action) => {
              setQueueAction(action);
              setActiveTab('queue');
            }}
          />
        )}

        {activeTab === 'queue' && <QueueTab initialAction={queueAction} />}

        {activeTab === 'policy' && <PolicyTab />}

        {activeTab === 'evaluation' && <EvaluationTab />}

        {activeTab === 'disputes' && (
          <WorkspaceTab
            disputes={disputes}
            investigation={investigation}
            loading={loading}
            llmEnabled={Boolean(llmMode?.enabled)}
            error={error}
            selectedCaseId={selectedCaseId}
            onSelectCase={setSelectedCaseId}
            searchTerm={searchTerm}
            onSearchChange={setSearchTerm}
            filterCategory={filterCategory}
            onFilterChange={setFilterCategory}
            selectedNode={selectedNode}
            onSelectNode={setSelectedNode}
            highlightedEvidenceId={highlightedEvidenceId}
            onCiteClick={citeEvidence}
            submission={submission}
            submitting={submitting}
            onSubmit={submitDecision}
            onResetSubmission={() => setSubmission(null)}
          />
        )}

      </main>
    </div>
  );
}
