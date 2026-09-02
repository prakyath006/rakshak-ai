import { RefreshCw } from 'lucide-react';
import { Wordmark } from './Wordmark';
import type { LLMMode, SystemMode, TabId } from '../types';

const TABS: Array<{ id: TabId; label: string; n: string }> = [
  { id: 'overview', label: 'Overview', n: '01' },
  { id: 'queue', label: 'Risk queue', n: '02' },
  { id: 'policy', label: 'Policy', n: '03' },
  { id: 'evaluation', label: 'Evaluation', n: '04' },
  { id: 'disputes', label: 'Disputes', n: '05' },
];

/**
 * The application's masthead, set as a document's running head rather than an
 * app chrome bar: a rule under the title, section tabs marked by the rule they
 * sit on, and a metadata strip stating what mode the system is actually in.
 */
export default function Header({
  activeTab,
  onTabChange,
  systemMode,
  llmMode,
  onRefresh,
  onExit,
}: {
  activeTab: TabId;
  onTabChange: (t: TabId) => void;
  systemMode: SystemMode | null;
  llmMode: LLMMode | null;
  onRefresh: () => void;
  onExit?: () => void;
}) {
  return (
    <header className="sticky top-0 z-40 bg-paper/95 backdrop-blur-sm">
      <div className="border-b-2 border-graphite-900">
        <div className="max-w-[104rem] mx-auto px-5 sm:px-7">
          <div className="flex items-center justify-between gap-6 py-3.5">
            <button
              onClick={onExit}
              title="Back to the site"
              className="text-graphite-900 hover:text-press transition-colors"
            >
              <Wordmark className="text-[.95rem]" sub="Risk manager" />
            </button>

            <div className="flex items-center gap-4">
              {/* Mode is stated in words, never implied by a colour alone. */}
              <div className="hidden md:flex items-center gap-4 note">
                {systemMode && (
                  <span title={systemMode.reason} className="flex items-center gap-2">
                    <span
                      className={`w-1.5 h-1.5 ${systemMode.simulated ? 'bg-warn' : 'bg-gain'}`}
                      aria-hidden
                    />
                    {systemMode.simulated ? 'Simulated — no live API calls' : 'Razorpay test API — live'}
                  </span>
                )}
                {llmMode && (
                  <span title={llmMode.reason} className="flex items-center gap-2 border-l border-paper-rule pl-4">
                    <span className={`w-1.5 h-1.5 ${llmMode.enabled ? 'bg-press' : 'bg-graphite-300'}`} aria-hidden />
                    {llmMode.enabled ? `Model: ${llmMode.model}` : 'Model off — rules only'}
                  </span>
                )}
              </div>

              <button
                onClick={onRefresh}
                className="p-1.5 text-graphite-500 hover:text-graphite-900 transition-colors"
                title="Refresh"
                aria-label="Refresh"
              >
                <RefreshCw className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Section tabs, marked by the rule they sit on. */}
      <nav aria-label="Sections" className="border-b border-paper-rule bg-paper">
        <div className="max-w-[104rem] mx-auto px-5 sm:px-7 flex gap-0 overflow-x-auto">
          {TABS.map(({ id, label, n }) => {
            const on = activeTab === id;
            return (
              <button
                key={id}
                onClick={() => onTabChange(id)}
                aria-current={on ? 'page' : undefined}
                className={`group flex items-baseline gap-2 px-4 py-3 whitespace-nowrap border-b-2 -mb-px transition-colors ${
 on
                    ? 'border-graphite-900 text-graphite-900'
                    : 'border-transparent text-graphite-500 hover:text-graphite-900'
                }`}
              >
                <span className="fig text-[.65rem] text-graphite-400">{n}</span>
                <span className={`text-[.85rem] ${on ? 'font-medium' : ''}`}>{label}</span>
              </button>
            );
          })}
        </div>
      </nav>
    </header>
  );
}
