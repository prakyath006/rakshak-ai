import { Activity } from 'lucide-react';
import type { DisputeSummary, InvestigationResult } from '../../types';
import { Card } from '../ui';

export function getDeadlineInfo(respondBy: string | undefined) {
  if (!respondBy) return { text: 'Unknown', urgency: 'normal' as const, hours: 999 };
  const deadline = new Date(respondBy);
  const diffMs = deadline.getTime() - Date.now();
  const diffHours = Math.max(0, Math.floor(diffMs / 3_600_000));
  const diffMins = Math.max(0, Math.floor((diffMs % 3_600_000) / 60_000));
  const text = diffMs <= 0 ? 'Deadline passed' : diffHours > 0 ? `${diffHours}h ${diffMins}m remaining` : `${diffMins}m remaining`;
  const urgency = diffMs <= 0 || diffHours < 6 ? ('critical' as const) : diffHours < 24 ? ('high' as const) : ('normal' as const);
  return { text, urgency, hours: diffHours };
}

const SCORES = [
  { key: 'completeness_score', label: 'Completeness', color: 'text-graphite-900' },
  { key: 'reliability_score', label: 'Reliability', color: 'text-gain' },
  { key: 'consistency_score', label: 'Consistency', color: 'text-[#8a6110]' },
  { key: 'relevance_score', label: 'Relevance', color: 'text-press' },
] as const;

export default function CaseSummaryPanel({
  investigation,
  dispute,
}: {
  investigation: InvestigationResult;
  dispute?: DisputeSummary;
}) {
  const dl = getDeadlineInfo(dispute?.respond_by);

  const deadlineTone =
    dl.urgency === 'critical'
      ? { box: 'bg-loss/[.08] border-loss/35', text: 'text-loss', label: 'CRITICAL' }
      : dl.urgency === 'high'
      ? { box: 'bg-warn/[.12] border-warn/50', text: 'text-[#8a6110]', label: 'HIGH PRIORITY' }
      : { box: 'bg-paper border-paper-rule', text: 'text-graphite-900', label: 'NORMAL' };

  return (
    <>
      <Card className="p-5 space-y-4">
        <div className="flex items-center justify-between gap-2 flex-wrap">
          <span className="font-mono text-xs font-bold text-press bg-press/[.08] px-2 py-0.5 rounded border border-press/25">
            {investigation.case_id}
          </span>
          <span className="text-xs font-semibold px-2 py-0.5 rounded bg-paper-sunk text-graphite-700">Phase: Chargeback</span>
        </div>

        <div>
          <div className="text-xs text-graphite-500">Disputed amount</div>
          <div className="text-2xl font-black text-graphite-900 font-mono tabular-nums">
            {dispute ? `₹${dispute.amount.toLocaleString('en-IN')}` : '—'}
          </div>
        </div>

        <div className={`p-3 border text-center ${deadlineTone.box}`}>
          <div className="text-2xs font-bold uppercase tracking-wider text-graphite-500">Response deadline</div>
          <div className={`text-lg font-black font-mono ${deadlineTone.text}`}>{dl.text}</div>
          <div className={`text-2xs font-bold uppercase ${dl.urgency === 'normal' ? 'text-graphite-400' : deadlineTone.text}`}>
            {deadlineTone.label}
          </div>
        </div>

        <div className="space-y-2 border-t border-paper-rule pt-3 text-xs">
          <div>
            <span className="text-graphite-400">Reason code: </span>
            <span className="font-mono font-bold text-graphite-900">
              {investigation.policy.reason_code} ({investigation.policy.network})
            </span>
          </div>
          <div>
            <span className="text-graphite-400">Description: </span>
            <span className="text-graphite-900">{investigation.policy.reason_description}</span>
          </div>
        </div>
      </Card>

      <Card className="p-5 space-y-3">
        <div className="text-xs font-bold text-graphite-700 uppercase tracking-wider flex items-center gap-1.5">
          <Activity className="w-3.5 h-3.5 text-press" />
          4D verification scores
        </div>
        <div className="grid grid-cols-2 gap-2 text-xs">
          {SCORES.map(({ key, label, color }) => (
            <div key={key} className="bg-paper p-2 border border-paper-rule">
              <div className="text-graphite-400 text-2xs">{label}</div>
              <div className={`font-mono font-bold tabular-nums ${color}`}>
                {(investigation.verification[key] * 100).toFixed(0)}%
              </div>
            </div>
          ))}
        </div>
      </Card>
    </>
  );
}
