import { useCallback, useEffect, useState } from 'react';
import { ChevronLeft, ChevronRight, Filter } from 'lucide-react';
import * as api from '../../api';
import type { QueueItem, QueuePage, RiskAction } from '../../types';
import { ACTION_LABELS } from '../../types';
import { ACTION_TONE, count, inr, pct } from '../../format';
import { Card } from '../ui';

const PAGE = 25;
const ACTIONS: RiskAction[] = ['APPROVE', 'STEP_UP', 'REVIEW', 'BLOCK'];

export default function QueueTab({ initialAction }: { initialAction?: string }) {
  const [page, setPage] = useState<QueuePage | null>(null);
  const [offset, setOffset] = useState(0);
  const [action, setAction] = useState<string | undefined>(initialAction);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<QueueItem | null>(null);

  useEffect(() => {
    setAction(initialAction);
    setOffset(0);
  }, [initialAction]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setPage(await api.fetchQueue({ limit: PAGE, offset, action }));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load queue');
    } finally {
      setLoading(false);
    }
  }, [offset, action]);

  useEffect(() => {
    load();
  }, [load]);

  const total = page?.total ?? 0;

  return (
    <div className="space-y-4">
      <Card className="p-4">
        <div className="flex flex-wrap items-center gap-3">
          <span className="text-xs text-graphite-500 flex items-center gap-1.5">
            <Filter className="w-3.5 h-3.5" /> Action
          </span>
          <div className="flex flex-wrap gap-1.5">
            <button
              onClick={() => { setAction(undefined); setOffset(0); }}
              className={`px-2.5 py-1 text-xs font-medium transition border ${
                !action ? 'bg-press text-paper border-press' : 'bg-paper border-paper-rule text-graphite-500 hover:text-graphite-900'
              }`}
            >
              All
            </button>
            {ACTIONS.map((a) => (
              <button
                key={a}
                onClick={() => { setAction(a); setOffset(0); }}
                className={`px-2.5 py-1 text-xs font-medium transition border ${
                  action === a
                    ? `${ACTION_TONE[a].bg} ${ACTION_TONE[a].text}`
                    : 'bg-paper border-paper-rule text-graphite-500 hover:text-graphite-900'
                }`}
              >
                {ACTION_LABELS[a]}
              </button>
            ))}
          </div>
          <span className="text-xs text-graphite-400 ml-auto font-mono tabular-nums">
            {count(total)} transactions · ranked by expected loss
          </span>
        </div>
      </Card>

      {error && (
        <div className="bg-loss/[.08] border border-loss/35 p-4 text-xs text-loss">{error}</div>
      )}

      <Card className="overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-xs min-w-[52rem]">
            <thead className="bg-paper text-graphite-500 uppercase text-2xs tracking-wider border-b border-paper-rule">
              <tr>
                <th className="text-left p-3 font-semibold">Transaction</th>
                <th className="text-right p-3 font-semibold">Amount</th>
                <th className="text-right p-3 font-semibold">P(chargeback)</th>
                <th className="text-right p-3 font-semibold">Expected loss</th>
                <th className="text-left p-3 font-semibold">Action</th>
                <th className="text-left p-3 font-semibold">Segment</th>
                <th className="text-left p-3 font-semibold">Outcome</th>
              </tr>
            </thead>
            <tbody className={`divide-y divide-paper-rule-soft ${loading ? 'opacity-50' : ''}`}>
              {page?.items.map((it) => (
                <tr
                  key={it.transaction_id}
                  onClick={() => setSelected(selected?.transaction_id === it.transaction_id ? null : it)}
                  className="hover:bg-paper cursor-pointer transition"
                >
                  <td className="p-3 font-mono text-press">{it.transaction_id}</td>
                  <td className="p-3 text-right font-mono tabular-nums text-graphite-900">{inr(it.amount_inr)}</td>
                  <td className="p-3 text-right">
                    <div className="flex items-center justify-end gap-2">
                      <div className="w-16 h-1.5 bg-paper-sunk rounded-full overflow-hidden hidden sm:block">
                        <div
                          className="h-full bg-press rounded-full"
                          style={{ width: `${Math.min(100, it.p_fraud * 100)}%` }}
                        />
                      </div>
                      <span className="font-mono tabular-nums text-graphite-700 w-12 text-right">
                        {pct(it.p_fraud, 1)}
                      </span>
                    </div>
                  </td>
                  <td className="p-3 text-right font-mono tabular-nums text-[#8a6110]">{inr(it.expected_loss_inr)}</td>
                  <td className="p-3">
                    <span className={`px-2 py-0.5 rounded border text-2xs font-semibold ${ACTION_TONE[it.action].bg} ${ACTION_TONE[it.action].text}`}>
                      {ACTION_LABELS[it.action]}
                    </span>
                  </td>
                  <td className="p-3 font-mono text-graphite-500">{it.segment ?? '—'}</td>
                  <td className="p-3">
                    {/* Ground truth is shown because this is a held-out evaluation
                        fold, not a live stream. Hiding it would be the dishonest choice. */}
                    <span className={it.is_fraud ? 'text-loss' : 'text-graphite-400'}>
                      {it.is_fraud ? 'chargeback' : 'clean'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="flex items-center justify-between gap-3 p-3 border-t border-paper-rule bg-paper">
          <span className="text-2xs text-graphite-400 font-mono tabular-nums">
            {count(offset + 1)}–{count(Math.min(offset + PAGE, total))} of {count(total)}
          </span>
          <div className="flex gap-1.5">
            <button
              onClick={() => setOffset(Math.max(0, offset - PAGE))}
              disabled={offset === 0}
              className="p-1.5 bg-paper-sunk hover:bg-paper-sunk disabled:opacity-40 disabled:cursor-not-allowed text-graphite-700 transition"
              aria-label="Previous page"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <button
              onClick={() => setOffset(offset + PAGE)}
              disabled={offset + PAGE >= total}
              className="p-1.5 bg-paper-sunk hover:bg-paper-sunk disabled:opacity-40 disabled:cursor-not-allowed text-graphite-700 transition"
              aria-label="Next page"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </Card>

      {selected && (
        <Card className="p-5">
          <div className="flex items-center justify-between gap-3 mb-3 flex-wrap">
            <h3 className="text-sm font-bold text-graphite-900 font-mono">Transaction {selected.transaction_id}</h3>
            <span className={`px-2 py-0.5 rounded border text-2xs font-semibold ${ACTION_TONE[selected.action].bg} ${ACTION_TONE[selected.action].text}`}>
              {ACTION_LABELS[selected.action]}
            </span>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4 text-xs">
            {[
              ['Amount', inr(selected.amount_inr)],
              ['P(chargeback)', pct(selected.p_fraud, 2)],
              ['Expected loss', inr(selected.expected_loss_inr)],
              ['Day in fold', String(selected.day)],
              ['Card', [selected.card_network, selected.card_type].filter(Boolean).join(' · ') || '—'],
              ['Email', selected.email_domain ?? '—'],
            ].map(([label, value]) => (
              <div key={label}>
                <div className="text-graphite-400 text-2xs uppercase tracking-wider">{label}</div>
                <div className="text-graphite-900 font-mono mt-0.5 break-words">{value}</div>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}
