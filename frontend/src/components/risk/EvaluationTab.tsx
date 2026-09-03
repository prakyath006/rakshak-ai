import { useEffect, useState } from 'react';
import { CheckCircle2, Target } from 'lucide-react';
import * as api from '../../api';
import type { ChartData, Evaluation, RiskStatus } from '../../types';
import { count, pct } from '../../format';
import { SEQUENTIAL } from '../../viz/palette';
import { Card, ChartSkeleton } from '../ui';
import { CalibrationPlot, PrCurve } from '../charts/Charts';

export default function EvaluationTab() {
  const [evaluation, setEvaluation] = useState<Evaluation | null>(null);
  const [status, setStatus] = useState<RiskStatus | null>(null);
  const [charts, setCharts] = useState<ChartData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.fetchEvaluation(), api.fetchRiskStatus(), api.fetchCharts()])
      .then(([ev, st, ch]) => {
        setEvaluation(ev);
        setStatus(st);
        setCharts(ch.available ? { ...ch, pr_auc: ev.pr_auc } : null);
      })
      .catch((e) => setError(e instanceof Error ? e.message : 'Failed to load evaluation'));
  }, []);

  if (error) {
    return <div className="bg-loss/[.08] border border-loss/35 p-4 text-xs text-loss">{error}</div>;
  }
  if (!evaluation?.available) {
    return <Card className="p-8 text-sm text-graphite-500">Loading evaluation…</Card>;
  }

  const bins = evaluation.calibration_bins || [];
  const features = evaluation.top_features || [];
  const maxGain = Math.max(...features.map((f) => f.gain), 1);

  return (
    <div className="space-y-6">
      <div className="bg-paper-raised border border-paper-rule px-4 py-2.5 flex flex-wrap items-center gap-x-5 gap-y-1.5 note">
        <span className="text-graphite-700 font-semibold">Measured once, on the final fold</span>
        <span>{count(evaluation.rows_test || 0)} transactions</span>
        <span>{pct(evaluation.fraud_rate_test || 0, 2)} fraudulent</span>
        <span className="text-graphite-400">{status?.split}</span>
      </div>

      {/* headline metrics */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <Card className="p-5">
          <div className="text-2xs font-semibold text-graphite-500 uppercase tracking-wider mb-1">PR-AUC</div>
          <div className="text-3xl font-extrabold font-mono tabular-nums text-graphite-900">
            {evaluation.pr_auc?.toFixed(4)}
          </div>
          <div className="text-xs text-gain mt-2">
            {evaluation.lift?.toFixed(1)}× the {evaluation.pr_auc_baseline?.toFixed(4)} baseline
          </div>
        </Card>
        <Card className="p-5">
          <div className="text-2xs font-semibold text-graphite-500 uppercase tracking-wider mb-1">
            Best precision
          </div>
          <div className="text-3xl font-extrabold font-mono tabular-nums text-gain">
            {pct(evaluation.operating_points?.[0]?.precision || 0, 1)}
          </div>
          <div className="text-xs text-graphite-500 mt-2">at a 0.5% review budget</div>
        </Card>
        <Card className="p-5">
          <div className="text-2xs font-semibold text-graphite-500 uppercase tracking-wider mb-1">
            Brier score
          </div>
          <div className="text-3xl font-extrabold font-mono tabular-nums text-graphite-900">
            {evaluation.brier_calibrated?.toFixed(4)}
          </div>
          <div className="text-xs text-graphite-500 mt-2">after isotonic calibration</div>
        </Card>
        <Card className="p-5">
          <div className="text-2xs font-semibold text-graphite-500 uppercase tracking-wider mb-1">ROC-AUC</div>
          <div className="text-3xl font-extrabold font-mono tabular-nums text-graphite-500">
            {evaluation.roc_auc?.toFixed(4)}
          </div>
          <div className="text-xs text-graphite-400 mt-2">context only — see note below</div>
        </Card>
      </div>

      {/* precision / recall — the brief's literal ask */}
      <Card className="p-5">
        <div className="flex items-start gap-2 mb-1">
          <Target className="w-4 h-4 text-press shrink-0 mt-0.5" />
          <h3 className="text-sm font-bold text-graphite-900">Precision and recall at real operating points</h3>
        </div>
        <p className="text-xs text-graphite-500 mb-4 max-w-3xl">
          Cut-offs are expressed as review budgets, because that is how a risk team actually sets
          one — an analyst desk can handle a fixed share of traffic per day, not “whatever scores
          above 0.5”.
        </p>
        <div className="overflow-x-auto">
          <table className="w-full text-xs min-w-[40rem]">
            <thead className="text-graphite-500 uppercase text-2xs tracking-wider">
              <tr className="border-b border-paper-rule">
                <th className="text-left py-2 font-semibold">Operating point</th>
                <th className="text-right py-2 font-semibold">Threshold</th>
                <th className="text-right py-2 font-semibold">Precision</th>
                <th className="text-right py-2 font-semibold">Recall</th>
                <th className="text-right py-2 font-semibold">Flagged</th>
                <th className="text-right py-2 font-semibold">False positives</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-paper-rule-soft">
              {evaluation.operating_points?.map((o) => (
                <tr key={o.name} className="hover:bg-paper transition">
                  <td className="py-2.5 text-graphite-900">{o.name}</td>
                  <td className="py-2.5 text-right font-mono tabular-nums text-graphite-500">{o.threshold.toFixed(4)}</td>
                  <td className="py-2.5 text-right font-mono tabular-nums text-gain font-semibold">{pct(o.precision, 1)}</td>
                  <td className="py-2.5 text-right font-mono tabular-nums text-graphite-900">{pct(o.recall, 1)}</td>
                  <td className="py-2.5 text-right font-mono tabular-nums text-graphite-500">{count(o.flagged)}</td>
                  <td className="py-2.5 text-right font-mono tabular-nums text-[#8a6110]">{count(o.false_positives)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="text-2xs text-graphite-400 mt-3">
          ROC-AUC is shown for context only. At a {pct(evaluation.fraud_rate_test || 0, 2)} positive
          rate the negative class dominates the false-positive-rate denominator, so ROC-AUC reads
          near 0.9 for models that are not much use. PR-AUC and the precision column are the honest
          summary.
        </p>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {charts ? (
          <Card className="p-5 sm:p-6">
            <PrCurve data={charts} />
          </Card>
        ) : (
          <ChartSkeleton />
        )}

        {/* features */}
        <Card className="p-5">
          <h3 className="text-sm font-bold text-graphite-900 mb-1">What the model is using</h3>
          <p className="text-xs text-graphite-500 mb-4">
            Features prefixed <code className="text-graphite-700">uid_</code> and{' '}
            <code className="text-graphite-700">account_day</code> come from reconstructing a latent
            account identity — the abuse-ring signal. They are not incidental.
          </p>
          <div className="space-y-1.5">
            {features.slice(0, 14).map((f) => {
              const isEntity = f.feature.startsWith('uid_') || f.feature === 'account_day';
              return (
                <div key={f.feature} className="flex items-center gap-2 text-2xs">
                  <span className={`w-32 shrink-0 font-mono truncate ${isEntity ? 'text-press font-semibold' : 'text-graphite-500'}`}>
                    {f.feature}
                  </span>
                  <div className="flex-1 h-2 bg-paper-sunk rounded-sm overflow-hidden">
                    <div
                      className="h-full rounded-sm"
                      style={{
                        width: `${(f.gain / maxGain) * 100}%`,
                        background: isEntity ? SEQUENTIAL[3] : SEQUENTIAL[0],
                      }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
          <p className="text-2xs text-graphite-400 mt-3 flex items-start gap-1.5">
            <CheckCircle2 className="w-3 h-3 shrink-0 mt-0.5 text-gain" />
            <span>
              All encoders were fitted on the training fold only. Concatenating folds before encoding
              would score higher and would not work in production.
            </span>
          </p>
        </Card>
      </div>

      {charts && bins.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          <Card className="p-5 sm:p-6">
            <CalibrationPlot bins={bins} />
          </Card>
          <Card className="p-5 sm:p-6">
            <h3 className="text-sm font-semibold text-graphite-900 mb-2">Why calibration is load-bearing here</h3>
            <p className="text-2xs text-graphite-700 leading-relaxed">
              The policy multiplies rupees by a probability. If the model says 5% and the truth is
              20%, the expected-cost arithmetic is wrong and every action it chooses is wrong with
              it — so calibration is not a nicety, it is what makes the money layer legal.
            </p>
            <p className="text-2xs text-graphite-700 leading-relaxed mt-3">
              The calibrator is isotonic and fitted on its own middle fold, never on the test fold.
              Fitting it on test would be scoring a correction using the data it was tuned against.
            </p>
            <div className="mt-4 pt-4 border-t border-paper-rule-soft flex gap-6 text-2xs">
              <div>
                <div className="text-graphite-400">Brier, raw</div>
                <div className="font-mono text-graphite-900">{evaluation.brier_raw?.toFixed(5)}</div>
              </div>
              <div>
                <div className="text-graphite-400">Brier, calibrated</div>
                <div className="font-mono text-gain">{evaluation.brier_calibrated?.toFixed(5)}</div>
              </div>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}
