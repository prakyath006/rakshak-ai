import { CheckCircle2, FileText, XCircle } from 'lucide-react';
import type { Rebuttal } from '../../types';
import { Card, PanelTitle } from '../ui';

function SourceBadge({ rebuttal }: { rebuttal: Rebuttal }) {
  const source = rebuttal.narrative_source;
  const tokens = rebuttal.llm_draft?.verification?.tokens_checked ?? 0;

  if (source === 'llm') {
    return (
      <span
        title="Model-written draft, verified token-by-token against the evidence graph."
        className="text-2xs px-2 py-0.5 rounded font-mono font-semibold bg-[#9085e9]/12 text-[#b4acf2] shrink-0"
      >
        LLM draft · {tokens} tokens verified
      </span>
    );
  }
  if (source === 'template_after_llm_rejected') {
    return (
      <span
        title="The model's draft contained facts absent from the evidence, so it was discarded."
        className="text-2xs px-2 py-0.5 rounded font-mono font-semibold bg-loss/[.08] text-loss shrink-0"
      >
        LLM draft rejected · template used
      </span>
    );
  }
  return (
    <span className="text-2xs px-2 py-0.5 rounded font-mono font-semibold bg-paper-sunk/40 text-graphite-500 shrink-0">
      Template narrative
    </span>
  );
}

export default function RebuttalPanel({
  rebuttal,
  onCiteClick,
}: {
  rebuttal: Rebuttal;
  onCiteClick: (evidenceId: string) => void;
}) {
  const draft = rebuttal.llm_draft;
  const rejected = rebuttal.narrative_source === 'template_after_llm_rejected';

  return (
    <Card className="p-5 space-y-3">
      <PanelTitle icon={<FileText className="w-4 h-4 text-press" />} right={<SourceBadge rebuttal={rebuttal} />}>
        Grounded rebuttal
      </PanelTitle>

      {draft?.reason && (
        <p className={`text-2xs break-words ${rejected ? 'text-loss' : 'text-graphite-400'}`}>{draft.reason}</p>
      )}

      {rejected && draft?.verification?.unsupported && draft.verification.unsupported.length > 0 && (
        <div className="bg-loss/[.08] border border-loss/30 p-3 space-y-1">
          <div className="text-2xs font-bold text-loss uppercase">Unsupported tokens in the discarded draft</div>
          {draft.verification.unsupported.map((u, i) => (
            <div key={i} className="text-2xs text-graphite-500">
              <span className="font-mono text-loss">{u.token}</span>
              <span className="text-graphite-400"> ({u.kind})</span> — {u.detail}
            </div>
          ))}
        </div>
      )}

      <div className="bg-paper p-4 border border-paper-rule text-xs text-graphite-700 leading-relaxed font-mono whitespace-pre-wrap break-words">
        {rebuttal.explanation.split(/(\[EV-[A-Za-z0-9_-]+\])/).map((part, index) => {
          if (part.startsWith('[EV-') && part.endsWith(']')) {
            const tag = part.slice(1, -1);
            return (
              <button
                key={index}
                onClick={() => onCiteClick(tag)}
                className="inline-flex items-center px-1.5 mx-0.5 rounded bg-press/15 text-press border border-press/40 hover:bg-press hover:text-graphite-900 font-bold transition text-2xs"
                title={`Inspect evidence source ${tag}`}
              >
                {tag}
              </button>
            );
          }
          return part;
        })}
      </div>

      {rebuttal.claims.length > 0 && (
        <div className="space-y-1.5 pt-1">
          <div className="text-2xs font-bold text-graphite-500 flex items-center justify-between gap-2">
            <span>Atomic claim verification ({rebuttal.claims.length})</span>
            <span className="text-gain shrink-0">
              {rebuttal.claims.filter((c) => c.is_grounded).length}/{rebuttal.claims.length} grounded
            </span>
          </div>

          {rebuttal.claims_check_structurally_guaranteed && (
            <p className="text-2xs text-graphite-400 italic">
              These claims are generated from the evidence nodes they cite, so this check cannot fail. The
              falsifiable grounding checks are the correspondence quotes and the LLM draft token check.
            </p>
          )}

          {rebuttal.claims.map((c, i) => (
            <div key={i} className="flex items-start gap-2 text-2xs bg-paper p-2 border border-paper-rule">
              {c.is_grounded ? (
                <CheckCircle2 className="w-3.5 h-3.5 text-gain shrink-0 mt-0.5" />
              ) : (
                <XCircle className="w-3.5 h-3.5 text-loss shrink-0 mt-0.5" />
              )}
              <div className="flex-1 min-w-0">
                <span className="text-graphite-700 break-words">{c.claim}</span>
                {c.evidence_ids.length > 0 && (
                  <div className="flex gap-1 mt-1 flex-wrap">
                    {c.evidence_ids.map((eid) => (
                      <button
                        key={eid}
                        onClick={() => onCiteClick(eid)}
                        className="text-[9px] font-mono bg-press/[.08] text-press px-1.5 py-0.5 rounded border border-press/25 hover:bg-press/20 transition"
                      >
                        {eid}
                      </button>
                    ))}
                  </div>
                )}
              </div>
              <span className="text-2xs font-mono text-graphite-400 shrink-0 tabular-nums">
                {(c.confidence * 100).toFixed(0)}%
              </span>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}
