import { Cpu } from 'lucide-react';
import type { InvestigationResult, SubmissionState } from '../../types';
import { Card } from '../ui';

const STAGE_ICON: Record<string, string> = {
  INGESTED: '📋',
  CLASSIFIED: '🏷️',
  EVIDENCE_SEARCH: '🔍',
  TEXT_EXTRACTION: '💬',
  EVIDENCE_VERIFIED: '✅',
  DECISION_READY: '⚡',
  SAFETY_GATE: '🛡️',
  PACKAGE_READY: '📦',
};

function Entry({ time, icon, children }: { time: string; icon: string; children: React.ReactNode }) {
  return (
    <div className="flex items-start gap-2 text-xs">
      <span className="font-mono text-graphite-400 shrink-0 w-16 tabular-nums">{time}</span>
      <span className="shrink-0">{icon}</span>
      <div className="text-graphite-700 min-w-0 break-words">{children}</div>
    </div>
  );
}

export default function AuditTrailPanel({
  investigation,
  submission,
}: {
  investigation: InvestigationResult;
  submission: SubmissionState | null;
}) {
  const now = new Date();
  const clock = (offsetFromEnd: number) => {
    const ts = new Date(now.getTime() - offsetFromEnd * 1000);
    return ts.toLocaleTimeString('en-IN', { hour12: false });
  };

  return (
    <Card className="p-5 space-y-3">
      <div className="text-xs font-bold text-graphite-700 uppercase tracking-wider flex items-center gap-1.5">
        <Cpu className="w-3.5 h-3.5 text-press" />
        Audit trail
      </div>
      <div className="space-y-1.5">
        {investigation.audit_trail.map((item, idx) => (
          <Entry
            key={idx}
            time={clock(investigation.audit_trail.length - idx)}
            icon={STAGE_ICON[item.stage] || '📋'}
          >
            {item.action}
          </Entry>
        ))}

        {submission?.ok && (
          <>
            <Entry time={clock(0)} icon="👤">
              <span className="text-gain font-bold">Human approved — {submission.action}</span>
            </Entry>
            <Entry time={clock(0)} icon={submission.simulated ? '🧪' : '💳'}>
              <span className={`font-bold ${submission.simulated ? 'text-[#8a6110]' : 'text-gain'}`}>
                {submission.simulated
                  ? 'Recorded in simulated mode (no API call)'
                  : 'Evidence submitted to Razorpay Disputes API'}
              </span>
            </Entry>
          </>
        )}

        {submission && !submission.ok && (
          <Entry time={clock(0)} icon="⛔">
            <span className="text-loss font-bold">Submission failed — no evidence sent</span>
          </Entry>
        )}
      </div>
    </Card>
  );
}
