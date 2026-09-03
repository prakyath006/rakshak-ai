import { useCallback, useEffect, useMemo, useState } from 'react';
import { RotateCcw, SlidersHorizontal } from 'lucide-react';
import * as api from '../../api';
import type { PolicyBand, RiskAction } from '../../types';
import { ACTION_LABELS } from '../../types';
import { ACTION_TONE, inr, pct } from '../../format';
import { Card } from '../ui';

/** Each control: the field, how to label it, and a plausible range to sweep. */
const CONTROLS: Array<{
  field: string;
  label: string;
  help: string;
  min: number;
  max: number;
  step: number;
  format: (n: number) => string;
}> = [
  {
    field: 'dispute_fee',
    label: 'Dispute fee',
    help: 'Flat fee per chargeback, independent of ticket size.',
    min: 0, max: 5000, step: 50, format: (n) => inr(n),
  },
  {
    field: 'false_decline_multiplier',
    label: 'False decline cost',
    help: 'Cost of refusing a good customer, as a multiple of the basket. Above 1 counts churn.',
    min: 0.25, max: 3, step: 0.05, format: (n) => `${n.toFixed(2)}× basket`,
  },
  {
    field: 'step_up_abandon_rate',
    label: 'Step-up abandonment',
    help: 'Share of legitimate customers who give up at a 3DS challenge.',
    min: 0, max: 0.3, step: 0.005, format: (n) => pct(n, 1),
  },
  {
    field: 'step_up_bypass_rate',
    label: 'Step-up bypass',
    help: 'Share of fraudsters who clear the challenge anyway.',
    min: 0, max: 0.5, step: 0.01, format: (n) => pct(n, 1),
  },
  {
    field: 'review_cost',
    label: 'Manual review cost',
    help: 'Fully-loaded analyst cost of one review.',
    min: 0, max: 2000, step: 25, format: (n) => inr(n),
  },
  {
    field: 'review_accuracy',
    label: 'Review accuracy',
    help: 'Probability the analyst reaches the correct verdict.',
    min: 0.5, max: 1, step: 0.01, format: (n) => pct(n, 0),
  },
  {
    field: 'vamp_marginal_cost',
    label: 'VAMP pressure',
    help: 'Acquirer cost attributed to one more dispute. Rises as the book nears a monitoring threshold.',
    min: 0, max: 5000, step: 50, format: (n) => inr(n),
  },
];

const TICKETS = [500, 2000, 4000, 20000, 100000];

export default function PolicyTab() {
  const [defaults, setDefaults] = useState<Record<string, number> | null>(null);
  const [values, setValues] = useState<Record<string, number>>({});
  const [amount, setAmount] = useState(4000);
  const [bands, setBands] = useState<PolicyBand[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.fetchPolicyDefaults()
      .then((d) => { setDefaults(d); setValues(d); })
      .catch((e) => setError(e instanceof Error ? e.message : 'Failed to load policy defaults'));
  }, []);

  const simulate = useCallback(async () => {
    if (!defaults) return;
    try {
      const result = await api.simulatePolicy(amount, values);
      setBands(result.bands);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Simulation failed');
    }
  }, [amount, values, defaults]);

  useEffect(() => {
    // Debounced so dragging a slider does not fire a request per pixel.
    const t = setTimeout(simulate, 120);
    return () => clearTimeout(t);
  }, [simulate]);

  const dirty = useMemo(
    () => defaults != null && CONTROLS.some((c) => values[c.field] !== defaults[c.field]),
    [values, defaults],
  );

  if (!defaults) {
    return <Card className="p-8 text-sm text-graphite-500">{error || 'Loading policy…'}</Card>;
  }

  return (
    <div className="space-y-6">
      <Card className="p-5">
        <div className="flex items-start gap-3">
          <SlidersHorizontal className="w-5 h-5 text-press shrink-0 mt-0.5" />
          <div>
            <h2 className="text-base font-bold text-graphite-900">Policy explorer</h2>
            <p className="text-xs text-graphite-500 mt-0.5 max-w-3xl">
              No threshold here was tuned. Expected cost is linear in the fraud probability, so the
              optimal action is the lower envelope of four straight lines and the boundaries fall out
              of the arithmetic. Every cost below is an <em>assumption</em> — move one and watch where
              the boundaries go.
            </p>
          </div>
        </div>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        {/* controls */}
        <Card className="lg:col-span-2 p-5 space-y-5">
          <div className="flex items-center justify-between gap-2">
            <h3 className="text-sm font-bold text-graphite-900">Cost assumptions</h3>
            {dirty && (
              <button
                onClick={() => setValues(defaults)}
                className="text-2xs text-graphite-500 hover:text-graphite-900 flex items-center gap-1 transition"
              >
                <RotateCcw className="w-3 h-3" /> Reset
              </button>
            )}
          </div>

          {CONTROLS.map((c) => (
            <div key={c.field}>
              <div className="flex items-baseline justify-between gap-2 mb-1">
                <label htmlFor={c.field} className="text-xs font-medium text-graphite-900">
                  {c.label}
                </label>
                <span className="text-xs font-mono tabular-nums text-press">
                  {c.format(values[c.field] ?? 0)}
                </span>
              </div>
              <input
                id={c.field}
                type="range"
                min={c.min}
                max={c.max}
                step={c.step}
                value={values[c.field] ?? 0}
                onChange={(e) => setValues({ ...values, [c.field]: Number(e.target.value) })}
                className="w-full accent-press cursor-pointer"
              />
              <p className="text-2xs text-graphite-400 mt-0.5">{c.help}</p>
            </div>
          ))}
        </Card>

        {/* result */}
        <div className="lg:col-span-3 space-y-4">
          <Card className="p-5">
            <div className="flex items-center justify-between gap-3 flex-wrap mb-4">
              <h3 className="text-sm font-bold text-graphite-900">Action by fraud probability</h3>
              <div className="flex gap-1">
                {TICKETS.map((t) => (
                  <button
                    key={t}
                    onClick={() => setAmount(t)}
                    className={`px-2 py-1 text-2xs font-mono transition border ${
                      amount === t
                        ? 'bg-press text-paper border-press'
                        : 'bg-paper border-paper-rule text-graphite-500 hover:text-graphite-900'
                    }`}
                  >
                    {inr(t)}
                  </button>
                ))}
              </div>
            </div>

            {/* The envelope, drawn to the 0-1 probability scale. */}
            <div className="flex h-12 overflow-hidden border border-paper-rule">
              {bands.map((b, i) => {
                const width = (b.to - b.from) * 100;
                const action = b.action as RiskAction;
                return (
                  <div
                    key={`${b.action}-${i}`}
                    style={{ width: `${width}%`, transition: 'width 180ms ease-out' }}
                    className={`${ACTION_TONE[action].dot} flex items-center justify-center overflow-hidden`}
                    title={`${ACTION_LABELS[action]}: ${pct(b.from, 2)} – ${pct(b.to, 2)}`}
                  >
                    {width > 12 && (
                      <span className="text-2xs font-bold text-paper px-1 truncate">
                        {ACTION_LABELS[action]}
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
            <div className="flex justify-between text-2xs text-graphite-400 font-mono mt-1">
              <span>0%</span><span>25%</span><span>50%</span><span>75%</span><span>100%</span>
            </div>

            <div className="mt-4 space-y-1.5">
              {bands.map((b, i) => {
                const action = b.action as RiskAction;
                return (
                  <div key={`row-${i}`} className="flex items-center justify-between text-xs">
                    <span className="flex items-center gap-2">
                      <span className={`w-2 h-2 rounded-full ${ACTION_TONE[action].dot}`} />
                      <span className="text-graphite-700">{ACTION_LABELS[action]}</span>
                    </span>
                    <span className="font-mono tabular-nums text-graphite-500">
                      {pct(b.from, 2)} → {pct(b.to, 2)}
                    </span>
                  </div>
                );
              })}
            </div>
          </Card>

          <Card className="p-5">
            <h3 className="text-sm font-bold text-graphite-900 mb-2">A result worth arguing with</h3>
            <p className="text-xs text-graphite-500 leading-relaxed">
              Drag <strong className="text-graphite-900">Dispute fee</strong> to zero and compare the
              approve band across ticket sizes: it stops moving. Every other cost scales with the
              basket, so they cancel — the flat fee is the only thing that makes small tickets
              riskier to approve than large ones. That contradicts the usual
              “bigger ticket, more caution” instinct, and it is the sort of conclusion a cost model
              produces and a hand-tuned threshold table never would.
            </p>
          </Card>

          {error && (
            <div className="bg-loss/[.08] border border-loss/35 p-3 text-xs text-loss">
              {error}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
