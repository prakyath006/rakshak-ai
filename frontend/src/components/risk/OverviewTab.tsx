import { useEffect, useState } from 'react';
import { ArrowDownRight, ChevronRight, Layers, TrendingDown } from 'lucide-react';
import * as api from '../../api';
import type { ChartData, MoneyReport, RiskAction, RiskStatus, RiskSummary, SegmentView } from '../../types';
import { bps, count, inr, inrCompact, pct } from '../../format';
import { Card, CountUp, ChartSkeleton, PanelTitle, Skeleton, Stat } from '../ui';
import { ACTION_FILL, CostCurve, RiskDistribution, SensitivityStrip } from '../charts/Charts';

export default function OverviewTab({ onOpenQueue }: { onOpenQueue: (action?: string) => void }) {
  const [status, setStatus] = useState<RiskStatus | null>(null);
  const [summary, setSummary] = useState<RiskSummary | null>(null);
  const [money, setMoney] = useState<MoneyReport | null>(null);
  const [segments, setSegments] = useState<SegmentView | null>(null);
  const [charts, setCharts] = useState<ChartData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      api.fetchRiskStatus(),
      api.fetchRiskSummary(),
      api.fetchMoney(),
      api.fetchSegments(),
      api.fetchCharts(),
    ])
      .then(([st, su, mo, se, ch]) => {
        setStatus(st);
        setSummary(su);
        setMoney(mo);
        setSegments(se);
        setCharts(ch.available ? ch : null);
      })
      .catch((e) => setError(e instanceof Error ? e.message : 'Failed to load risk data'));
  }, []);

  if (error) {
    return (
      <div className="bg-loss/[.06] border border-loss/40 p-4 text-xs text-loss">{error}</div>
    );
  }

  const loading = !status;
  const policy = money?.strategies?.find((s) => s.name === 'cost-optimal policy');
  const baseline = money?.strategies?.find((s) => s.name === money?.best_baseline);
  const actions = summary?.actions || {};
  const totalActions = Object.values(actions).reduce((a, b) => a + b, 0) || 1;

  return (
    <div className="space-y-5">
      {/* provenance — the first thing a reviewer should be able to check */}
      <div className="bg-paper-raised border border-paper-rule px-4 py-2.5 flex flex-wrap items-center gap-x-5 gap-y-1.5 note">
        <span className="text-graphite-900 font-semibold flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-full bg-gain" />
          Held-out fold
        </span>
        {loading ? (
          <Skeleton className="h-3 w-96" />
        ) : (
          <>
            <span className="font-mono text-graphite-700">{count(status.rows_test || 0)} transactions</span>
            <span>final {status.fold_days} days</span>
            <span>trained on {count(status.rows_train || 0)} · calibrated on {count(status.rows_calib || 0)}</span>
            <span className="text-graphite-400">{status.split}</span>
            <span className="text-graphite-400 hidden xl:inline">{status.dataset}</span>
          </>
        )}
      </div>

      {/* headline */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4 stagger">
        <Stat
          accent
          label="Saved per 1,000 transactions"
          tone="gain"
          value={
            summary?.saving_per_1k_inr != null
              ? <CountUp value={summary.saving_per_1k_inr} format={(n) => inr(n)} />
              : <Skeleton className="h-7 w-32" />
          }
          sub={
            money?.best_baseline && (
              <span className="flex items-center gap-1.5 text-gain">
                <TrendingDown className="w-3.5 h-3.5" />
                {pct(summary?.saving_pct || 0)} cheaper than the best baseline
              </span>
            )
          }
        />
        <Stat
          label="Fraud let through"
          value={policy ? <CountUp value={policy.fraud_approved} format={(n) => count(Math.round(n))} /> : <Skeleton className="h-7 w-20" />}
          sub={
            baseline && (
              <span className="flex items-center gap-1.5">
                <ArrowDownRight className="w-3.5 h-3.5 text-gain" />
                {pct(1 - policy!.fraud_approved / baseline.fraud_approved)} fewer than baseline
              </span>
            )
          }
        />
        <Stat
          label="Good customers blocked"
          value={policy ? <CountUp value={policy.legit_blocked} format={(n) => count(Math.round(n))} /> : <Skeleton className="h-7 w-20" />}
          sub={
            baseline && (
              <span className="flex items-center gap-1.5">
                <ArrowDownRight className="w-3.5 h-3.5 text-gain" />
                {pct(1 - policy!.legit_blocked / baseline.legit_blocked)} fewer than baseline
              </span>
            )
          }
        />
        <Stat
          label="Value processed"
          value={summary?.value_inr != null ? <CountUp value={summary.value_inr} format={inrCompact} /> : <Skeleton className="h-7 w-28" />}
          sub={summary && `${pct(summary.fraud_rate || 0, 2)} of transactions ended in a chargeback`}
        />
      </div>

      {/* the hero picture */}
      {charts ? (
        <Card className="p-5 sm:p-6 animate-rise">
          <RiskDistribution data={charts} />
        </Card>
      ) : (
        <ChartSkeleton />
      )}

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
        {charts ? (
          <Card className="p-5 sm:p-6">
            <CostCurve data={charts} />
          </Card>
        ) : (
          <ChartSkeleton />
        )}

        {/* strategy comparison */}
        <Card className="p-5 sm:p-6">
          <PanelTitle sub="A single threshold can only trade one error against the other. Pricing each action lets the policy do better on both at once.">
            Better on both errors
          </PanelTitle>
          {money?.strategies ? (
            <div className="overflow-x-auto -mx-1 px-1">
              <table className="w-full text-2xs min-w-[30rem]">
                <thead className="text-graphite-500 uppercase tracking-[.06em]">
                  <tr className="border-b border-paper-rule">
                    <th className="text-left py-2 font-medium">Strategy</th>
                    <th className="text-right py-2 font-medium">₹ / 1k</th>
                    <th className="text-right py-2 font-medium">Fraud thru</th>
                    <th className="text-right py-2 font-medium">Good blocked</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-paper-rule-soft">
                  {money.strategies.map((s) => {
                    const isPolicy = s.name === 'cost-optimal policy';
                    return (
                      <tr
                        key={s.name}
                        className={`transition-colors ${isPolicy ? 'bg-gain/[.07]' : 'hover:bg-paper'}`}
                      >
                        <td className={`py-2.5 ${isPolicy ? 'text-gain font-semibold' : 'text-graphite-900'}`}>
                          {s.name}
                        </td>
                        <td className="py-2.5 text-right font-mono text-graphite-900">{inr(s.cost_per_1k_inr)}</td>
                        <td className="py-2.5 text-right font-mono text-graphite-700">{count(s.fraud_approved)}</td>
                        <td className="py-2.5 text-right font-mono text-graphite-700">{count(s.legit_blocked)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="space-y-2">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-8 w-full" />)}</div>
          )}

          {charts?.sensitivity && (
            <div className="mt-6 pt-6 border-t border-paper-rule-soft">
              <SensitivityStrip data={charts} />
            </div>
          )}
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-5">
        {/* action mix */}
        <Card className="lg:col-span-2 p-5 sm:p-6">
          <PanelTitle sub="Click a band to inspect those transactions.">What the policy did</PanelTitle>

          <div className="flex h-2.5 rounded-full overflow-hidden mb-5 gap-[2px]">
            {(['APPROVE', 'STEP_UP', 'REVIEW', 'BLOCK'] as RiskAction[]).map((a) => {
              const share = (actions[a] || 0) / totalActions;
              if (share <= 0) return null;
              return (
                <button
                  key={a}
                  onClick={() => onOpenQueue(a)}
                  title={`${a}: ${count(actions[a])} (${pct(share, 2)})`}
                  style={{
                    width: `${share * 100}%`,
                    background: ACTION_FILL[a],
                    transition: 'width .8s cubic-bezier(.16,1,.3,1), opacity .15s',
                  }}
                  className="hover:opacity-75 rounded-sm"
                />
              );
            })}
          </div>

          <div className="space-y-0.5">
            {(['APPROVE', 'STEP_UP', 'REVIEW', 'BLOCK'] as RiskAction[]).map((a) => (
              <button
                key={a}
                onClick={() => onOpenQueue(a)}
                className="w-full flex items-center justify-between gap-3 text-xs py-1.5 px-2 -mx-2 hover:bg-paper transition group"
              >
                <span className="flex items-center gap-2.5">
                  <span className="w-2 h-2 rounded-full" style={{ background: ACTION_FILL[a] }} />
                  <span className="text-graphite-900">{a.replace('_', '-').toLowerCase()}</span>
                </span>
                <span className="flex items-center gap-2 font-mono text-graphite-700">
                  {count(actions[a] || 0)}
                  <span className="text-graphite-400 w-12 text-right">{pct((actions[a] || 0) / totalActions, 2)}</span>
                  <ChevronRight className="w-3.5 h-3.5 text-graphite-300 group-hover:text-graphite-700 group-hover:translate-x-0.5 transition" />
                </span>
              </button>
            ))}
          </div>
        </Card>

        {/* portfolio segments */}
        <Card className="lg:col-span-3 p-5 sm:p-6">
          <PanelTitle
            icon={<Layers className="w-4 h-4 text-press" />}
            sub="Ranked by contribution to the whole book, not by each segment's own rate. The two disagree — and only the first tells you where effort belongs."
          >
            Where the disputes come from
          </PanelTitle>

          <div className="space-y-2.5">
            {segments?.segments?.map((s) => {
              const maxContrib = Math.max(...segments.segments.map((x) => x.portfolio_bps_contributed), 1);
              return (
                <div key={s.segment} className="group">
                  <div className="flex items-center justify-between gap-3 text-2xs mb-1">
                    <span className="font-mono text-graphite-900 w-6">{s.segment}</span>
                    <div className="flex-1 flex items-center gap-3 justify-end text-graphite-500">
                      <span>own <span className="font-mono text-graphite-700">{bps(s.own_rate_bps)}</span></span>
                      <span className="text-graphite-900 font-mono font-semibold w-20 text-right">
                        {bps(s.portfolio_bps_contributed, 1)}
                      </span>
                      <span className="text-gain font-mono w-16 text-right">→ {bps(s.residual_rate_bps)}</span>
                    </div>
                  </div>
                  <div className="h-1.5 bg-paper-sunk rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full bg-press group-hover:bg-press/70 transition-colors"
                      style={{
                        width: `${(s.portfolio_bps_contributed / maxContrib) * 100}%`,
                        transition: 'width .9s cubic-bezier(.16,1,.3,1), background-color .15s',
                      }}
                    />
                  </div>
                </div>
              );
            }) || [0, 1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-8 w-full" />)}
          </div>

          <p className="text-2xs text-graphite-400 mt-4 leading-relaxed">
            Bar length is basis points added to the book. IEEE-CIS has no merchant column, so{' '}
            <code className="text-graphite-500">ProductCD</code> stands in as the segment — the arithmetic is
            identical, only the noun changes.
          </p>
        </Card>
      </div>
    </div>
  );
}
