import { AlertTriangle, CheckCircle2, XCircle } from 'lucide-react';
import type { InvestigationResult } from '../../types';
import { Card, PanelTitle } from '../ui';

export default function VerificationMatrixPanel({ investigation }: { investigation: InvestigationResult }) {
  const { verification, policy, decision } = investigation;

  return (
    <Card className="p-5 space-y-3">
      <PanelTitle
        icon={<CheckCircle2 className="w-4 h-4 text-gain" />}
        right={
          <span className="text-xs font-mono font-bold text-graphite-900 shrink-0">
            Strength: {decision.evidence_strength}
          </span>
        }
      >
        Policy verification matrix
      </PanelTitle>

      {verification.contradictions.length > 0 && (
        <div className="bg-loss/[.08] border border-loss/35 p-3 text-xs space-y-1">
          <div className="font-bold flex items-center gap-1.5 text-loss">
            <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
            Evidence contradiction detected
          </div>
          {verification.contradictions.map((c, i) => (
            <div key={i} className="pl-5 text-graphite-700">
              • {c}
            </div>
          ))}
        </div>
      )}

      {verification.relevance_warnings.length > 0 && (
        <div className="bg-warn/[.12] border border-warn/50 p-3 text-xs space-y-1">
          <div className="font-bold flex items-center gap-1.5 text-[#8a6110]">
            <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
            Irrelevant evidence excluded
          </div>
          {verification.relevance_warnings.map((w, i) => (
            <div key={i} className="pl-5 text-graphite-700">
              • {w}
            </div>
          ))}
        </div>
      )}

      <div className="space-y-1.5">
        {policy.required_evidence.map((req) => {
          const isPresent = verification.summary_by_type[req.type] === 'PRESENT';
          return (
            <div
              key={req.type}
              className="flex items-center justify-between gap-2 p-2 bg-paper border border-paper-rule text-xs"
            >
              <div className="flex items-center gap-2 min-w-0">
                {isPresent ? (
                  <CheckCircle2 className="w-4 h-4 text-gain shrink-0" />
                ) : (
                  <XCircle className="w-4 h-4 text-loss shrink-0" />
                )}
                <span className={`truncate ${isPresent ? 'text-graphite-900 font-medium' : 'text-graphite-500'}`}>
                  {req.description || req.type}
                </span>
              </div>
              <span
                className={`text-2xs font-bold px-2 py-0.5 rounded shrink-0 ${
 isPresent ? 'bg-gain/[.07]12 text-gain' : 'bg-loss/[.08] text-loss'
                }`}
              >
                {isPresent ? 'PRESENT' : req.critical ? 'CRITICAL MISSING' : 'OPTIONAL MISSING'}
              </span>
            </div>
          );
        })}
      </div>
    </Card>
  );
}
