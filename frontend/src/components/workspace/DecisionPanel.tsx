import { AlertTriangle, CheckCircle2, ShieldAlert, XCircle } from 'lucide-react';
import type { InvestigationResult } from '../../types';
import { DECISION_LABELS } from '../../types';

const TONE = {
  CONTEST: { box: 'bg-gain/[.07] border-gain/35', text: 'text-gain' },
  DO_NOT_CONTEST: { box: 'bg-loss/[.07] border-loss/35', text: 'text-loss' },
  REVIEW: { box: 'bg-warn/[.07] border-warn/50', text: 'text-[#8a6110]' },
};

export default function DecisionPanel({ investigation }: { investigation: InvestigationResult }) {
  const { decision } = investigation;
  const tone = TONE[decision.recommendation] ?? TONE.REVIEW;
  const exp = decision.structured_explanation;
  const downgraded = exp?.downgraded_from;

  return (
    <div className={`p-5 border ${tone.box}`}>
      <div className="text-2xs font-bold uppercase tracking-wider text-graphite-500 mb-1">AI recommendation</div>
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div className={`text-xl font-black tracking-tight ${tone.text}`}>
          {DECISION_LABELS[decision.recommendation]}
        </div>
        <div className="text-xs font-mono font-bold px-2 py-1 rounded bg-paper-sunk text-graphite-900 border border-paper-rule shrink-0">
          Confidence {(decision.confidence * 100).toFixed(0)}%
        </div>
      </div>
      <p className="text-xs text-graphite-700 mt-2 leading-relaxed font-medium">{decision.reasoning}</p>

      {downgraded && (
        <div className="mt-3 bg-loss/[.08] border border-loss/35 p-3 text-xs">
          <div className="font-bold text-loss flex items-center gap-1.5">
            <ShieldAlert className="w-3.5 h-3.5 shrink-0" />
            Safety gate: downgraded from {downgraded}
          </div>
          <p className="text-loss/80 mt-1">
            Verified correspondence contradicted the evidence-based defence. The gate can only move a decision
            toward review — it can never create a contest.
          </p>
        </div>
      )}

      {exp && (
        <div className="mt-3 pt-3 border-t border-paper-rule space-y-2">
          <div className="text-2xs font-bold text-graphite-500 uppercase tracking-wider">Why this decision?</div>

          {exp.key_findings.map((f, i) => (
            <div key={`k${i}`} className="flex items-start gap-1.5 text-xs">
              <CheckCircle2 className="w-3.5 h-3.5 text-gain shrink-0 mt-0.5" />
              <span className="text-graphite-700">{f}</span>
            </div>
          ))}

          {exp.contradictions.map((c, i) => (
            <div key={`c${i}`} className="flex items-start gap-1.5 text-xs">
              <AlertTriangle className="w-3.5 h-3.5 text-loss shrink-0 mt-0.5" />
              <span className="text-loss">{c}</span>
            </div>
          ))}

          {exp.missing_critical.map((m, i) => (
            <div key={`m${i}`} className="flex items-start gap-1.5 text-xs">
              <XCircle className="w-3.5 h-3.5 text-[#8a6110] shrink-0 mt-0.5" />
              <span className="text-[#8a6110]">Missing: {m}</span>
            </div>
          ))}

          <div className="pt-2 border-t border-paper-rule">
            <div className="text-2xs font-bold text-graphite-400 uppercase mb-1.5">Safety checks</div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-1">
              {Object.entries(exp.safety_checks).map(([key, val]) => {
                const pass = val.startsWith('PASS');
                return (
                  <div key={key} className="flex items-center gap-1.5 text-2xs">
                    <span className={pass ? 'text-gain' : 'text-loss'} aria-hidden>
                      {pass ? '✓' : '⚠'}
                    </span>
                    <span className="text-graphite-500">
                      {key.replace(/_/g, ' ')}
                      <span className="sr-only">: {pass ? 'pass' : 'flagged'}</span>
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
