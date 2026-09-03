import { CheckCircle2, Send, ShieldAlert, XCircle } from 'lucide-react';
import type { InvestigationResult, SubmissionState } from '../../types';
import { Card } from '../ui';

export default function ApprovalGatePanel({
  investigation,
  submission,
  submitting,
  onSubmit,
  onReset,
}: {
  investigation: InvestigationResult;
  submission: SubmissionState | null;
  submitting: boolean;
  onSubmit: (action: 'CONTEST' | 'ACCEPT' | 'ESCALATE', notes?: string) => void;
  onReset: () => void;
}) {
  const rec = investigation.decision.recommendation;

  return (
    <Card className="p-5 space-y-3">
      <div className="text-xs font-bold text-graphite-700 uppercase tracking-wider flex items-center justify-between gap-2 flex-wrap">
        <span>Human approval gate</span>
        <span className="text-2xs font-mono text-press">PATCH /v1/disputes/:id/contest</span>
      </div>

      {submission ? (
        submission.ok ? (
          <div
            className={`p-4 text-center space-y-1 border ${
              submission.simulated ? 'bg-warn/[.12] border-warn/50' : 'bg-gain/[.07]10 border-gain/40'
            }`}
          >
            <CheckCircle2 className={`w-6 h-6 mx-auto ${submission.simulated ? 'text-[#8a6110]' : 'text-gain'}`} />
            <div className={`text-xs font-bold ${submission.simulated ? 'text-[#8a6110]' : 'text-gain'}`}>
              {submission.simulated
                ? 'Recorded — SIMULATED, not sent to Razorpay'
                : 'Submitted to the Razorpay Disputes API'}
            </div>
            <div className="text-2xs text-graphite-500 break-words">{submission.message}</div>
            <div className="text-2xs text-graphite-400 font-mono break-all">
              {investigation.dispute_id} · {submission.action}
            </div>
          </div>
        ) : (
          <div className="bg-loss/[.08] border border-loss/40 p-4 space-y-2">
            <div className="flex items-center gap-2 text-xs font-bold text-loss">
              <XCircle className="w-4 h-4 shrink-0" /> Submission failed
            </div>
            <p className="text-2xs text-loss/80 break-words">{submission.error}</p>
            <button
              onClick={onReset}
              className="w-full py-1.5 bg-paper-sunk hover:bg-paper-sunk text-graphite-900 text-2xs font-semibold transition"
            >
              Try again
            </button>
          </div>
        )
      ) : (
        <div className="space-y-2">
          {rec === 'CONTEST' && (
            <button
              onClick={() => onSubmit('CONTEST')}
              disabled={submitting}
              className="w-full py-2.5 bg-gain hover:brightness-110 disabled:opacity-50 disabled:cursor-not-allowed text-paper text-xs font-bold transition flex items-center justify-center gap-2"
            >
              <Send className="w-3.5 h-3.5" />
              {submitting ? 'Submitting…' : 'Approve & submit representment package'}
            </button>
          )}

          {rec === 'REVIEW' && (
            <button
              onClick={() => onSubmit('ESCALATE', 'Manual analyst review')}
              disabled={submitting}
              className="w-full py-2.5 bg-[#8a6110] hover:brightness-110 disabled:opacity-50 disabled:cursor-not-allowed text-paper text-xs font-bold transition flex items-center justify-center gap-2"
            >
              <ShieldAlert className="w-3.5 h-3.5" />
              {submitting ? 'Escalating…' : 'Escalate for merchant analyst review'}
            </button>
          )}

          {rec === 'DO_NOT_CONTEST' && (
            <button
              onClick={() => onSubmit('ACCEPT')}
              disabled={submitting}
              className="w-full py-2.5 bg-paper-sunk hover:bg-paper-sunk disabled:opacity-50 disabled:cursor-not-allowed text-loss border border-loss/30 text-xs font-bold transition flex items-center justify-center gap-2"
            >
              <XCircle className="w-3.5 h-3.5" />
              {submitting ? 'Accepting…' : 'Accept dispute — no defensible evidence'}
            </button>
          )}

          <p className="text-2xs text-graphite-400 text-center">
            Requires verified merchant approval before any irreversible API submission.
          </p>
        </div>
      )}
    </Card>
  );
}
