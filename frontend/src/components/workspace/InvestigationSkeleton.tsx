import { Cpu } from 'lucide-react';
import { Card } from '../ui';

const STAGES = [
  'Classifying reason code',
  'Building evidence graph',
  'Reading correspondence (model)',
  'Verifying evidence',
  'Deciding',
  'Drafting representment (model)',
];

/**
 * Shown while an investigation is in flight.
 *
 * With the model enabled a contest case takes 8-15s — two sequential model calls,
 * one to read the correspondence and one to draft the representment. A bare
 * spinner for that long reads as a hang, so name the stages and say why it is slow.
 */
export default function InvestigationSkeleton({ llmEnabled }: { llmEnabled: boolean }) {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 xl:gap-6">
      <div className="lg:col-span-3 space-y-4">
        <Card className="p-5 space-y-3">
          <div className="h-4 w-24 rounded bg-paper-sunk animate-pulse" />
          <div className="h-8 w-40 rounded bg-paper-sunk animate-pulse" />
          <div className="h-16 bg-paper animate-pulse" />
        </Card>
        <Card className="p-5 space-y-2">
          {STAGES.map((stage, i) => (
            <div key={stage} className="flex items-center gap-2 text-xs">
              <span
                className="w-1.5 h-1.5 rounded-full bg-press animate-pulse"
                style={{ animationDelay: `${i * 180}ms` }}
              />
              <span className="text-graphite-500">{stage}</span>
            </div>
          ))}
        </Card>
      </div>

      <div className="lg:col-span-5 space-y-4">
        <Card className="p-5 space-y-4">
          <div className="h-4 w-48 rounded bg-paper-sunk animate-pulse" />
          <div className="h-40 bg-paper animate-pulse" />
        </Card>
      </div>

      <div className="lg:col-span-4 space-y-4">
        <Card className="p-5 space-y-3">
          <div className="h-4 w-32 rounded bg-paper-sunk animate-pulse" />
          <div className="h-20 bg-paper animate-pulse" />
        </Card>
        {llmEnabled && (
          <p className="text-2xs text-graphite-400 flex items-start gap-1.5 px-1">
            <Cpu className="w-3.5 h-3.5 shrink-0 mt-0.5 text-[#b4acf2]" />
            <span>
              Two model calls run in sequence — reading the support thread, then drafting the
              representment — so a contest case takes roughly 8–15 seconds. Set{' '}
              <code className="text-graphite-500">LLM_PROVIDER=none</code> for the sub-second
              deterministic path.
            </span>
          </p>
        )}
      </div>
    </div>
  );
}
