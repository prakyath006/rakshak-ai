import { Cpu } from 'lucide-react';
import type { ExtractionResult } from '../../types';
import { Card, PanelTitle } from '../ui';

const FLAG_TONE = {
  blocking: 'bg-loss/[.08] border-loss/35 text-loss',
  caution: 'bg-warn/[.12] border-warn/50 text-[#8a6110]',
  info: 'bg-paper border-paper-rule text-graphite-500',
};

export default function ExtractionPanel({ extraction }: { extraction: ExtractionResult }) {
  const qv = extraction.quote_verification;
  const hasRejections = qv.rejected > 0;

  return (
    <Card className="p-5 space-y-3">
      <PanelTitle
        icon={<Cpu className="w-4 h-4 text-[#b4acf2]" />}
        right={
          extraction.enabled && qv.proposed > 0 ? (
            <span
              title="Every signal must quote a verbatim span of the source message. Quotes that are not actually there are rejected."
              className={`text-2xs px-2 py-0.5 rounded font-mono font-semibold shrink-0 ${
 hasRejections ? 'bg-warn/[.12] text-[#8a6110]' : 'bg-gain/[.07]12 text-gain'
              }`}
            >
              {qv.verbatim}/{qv.proposed} quotes verified
            </span>
          ) : undefined
        }
      >
        Correspondence reading
      </PanelTitle>

      {!extraction.enabled ? (
        <p className="text-2xs text-graphite-400">{extraction.reason}</p>
      ) : (
        <>
          {extraction.claim_summary && (
            <p className="text-2xs text-graphite-500 italic">{extraction.claim_summary}</p>
          )}

          {extraction.signals.length === 0 && extraction.rejected_signals.length === 0 && (
            <p className="text-2xs text-graphite-400">
              {qv.neutral > 0
                ? `Model read the correspondence and found nothing decision-relevant (${qv.neutral} neutral).`
                : 'No decision-relevant signals found in the correspondence.'}
            </p>
          )}

          {extraction.signals.map((sig, i) => (
            <div key={`sig-${i}`} className="bg-paper border border-paper-rule p-3 space-y-1">
              <div className="flex items-center justify-between gap-2 flex-wrap">
                <span className="text-2xs font-bold text-[#b4acf2] font-mono">{sig.signal}</span>
                <span className="text-2xs text-graphite-400 font-mono">{sig.communication_id}</span>
              </div>
              <blockquote className="text-2xs text-graphite-700 border-l-2 border-[#9085e9]/40 pl-2 italic break-words">
                “{sig.quote}”
              </blockquote>
              {sig.reasoning && <p className="text-2xs text-graphite-400">{sig.reasoning}</p>}
            </div>
          ))}

          {extraction.rejected_signals.length > 0 && (
            <div className="pt-2 border-t border-paper-rule space-y-1">
              <div className="text-2xs font-bold text-loss uppercase">
                Rejected as ungrounded ({extraction.rejected_signals.length})
              </div>
              {extraction.rejected_signals.map((rej, i) => (
                <div key={`rej-${i}`} className="text-2xs text-graphite-400 break-words">
                  <span className="text-loss/80 font-mono">{rej.signal || 'unknown'}</span>
                  {' — '}
                  {rej.rejection}
                </div>
              ))}
            </div>
          )}

          {extraction.advisory_flags.length > 0 && (
            <div className="pt-2 border-t border-paper-rule space-y-1.5">
              {extraction.advisory_flags.map((flag, i) => (
                <div key={`flag-${i}`} className={`text-2xs px-2.5 py-1.5 border ${FLAG_TONE[flag.severity]}`}>
                  <span className="font-bold font-mono text-2xs">{flag.flag}</span>
                  <span className="block mt-0.5">{flag.detail}</span>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </Card>
  );
}
