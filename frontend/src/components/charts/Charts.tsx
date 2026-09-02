import { useEffect, useMemo, useRef, useState } from 'react';
import type { ChartData, RiskAction } from '../../types';
import { count, inr, pct } from '../../format';

/* --------------------------------------------------------------------------
 * Charts, drawn for paper.
 *
 * Line art, not filled dashboards: ink marks, hairline grids, printed rules for
 * boundaries. One scale places every mark and label; every axis label names a
 * value the chart reaches; text takes ink colours rather than a series colour.
 * Each chart carries a hover layer with a readout line beneath it, because an
 * SVG chart in a browser is interactive and ought to behave so.
 *
 * Colours were validated against the paper ground (#f2f4f6) rather than picked:
 * three of the four categorical slots fell below 3:1 contrast, so the marks use
 * ink plus a single deep red and a single press blue, which clear it.
 * ------------------------------------------------------------------------ */

const INK = '#0f1319';
const INK_2 = '#2c3540';
const MUTED = '#5a6675';
const FAINT = '#a3adb8';
const GRID = '#e2e7ec';
const PRESS = '#1b4d8f';
const LOSS = '#a6303c';
const GAIN = '#1f6b4a';

export const ACTION_FILL: Record<RiskAction, string> = {
  APPROVE: GAIN,
  STEP_UP: PRESS,
  REVIEW: '#8a6110',
  BLOCK: LOSS,
};

function useDrawn() {
  /** Path length, so `.draw` animates a stroke matching its own geometry. */
  const ref = useRef<SVGPathElement>(null);
  const [len, setLen] = useState(0);
  useEffect(() => {
    if (ref.current) setLen(ref.current.getTotalLength());
  }, []);
  return { ref, style: { ['--len' as string]: `${len}` } };
}

function Frame({
  title,
  subtitle,
  children,
  right,
  readout,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  right?: React.ReactNode;
  readout?: React.ReactNode;
}) {
  return (
    <figure className="m-0">
      <figcaption className="flex items-start justify-between gap-4 mb-4">
        <div className="min-w-0">
          <h3 className="font-display text-[1.15rem] leading-tight tracking-[-.01em]">{title}</h3>
          {subtitle && <p className="note mt-2 leading-relaxed max-w-[42rem]">{subtitle}</p>}
        </div>
        {right}
      </figcaption>
      {children}
      {/* Fixed-height readout so hovering never reflows the page. */}
      <div className="min-h-[1.6rem] mt-2 note">{readout}</div>
    </figure>
  );
}

/* ========================================================================== */
/* Precision-recall                                                           */
/* ========================================================================== */
export function PrCurve({ data }: { data: ChartData }) {
  const W = 620, H = 320, P = { t: 14, r: 16, b: 40, l: 50 };
  const iw = W - P.l - P.r, ih = H - P.t - P.b;
  const [hover, setHover] = useState<number | null>(null);
  const drawn = useDrawn();

  const pts = data.pr_curve;
  const x = (r: number) => P.l + r * iw;
  const y = (p: number) => P.t + (1 - p) * ih;

  const path = useMemo(
    () => pts.map((d, i) => `${i ? 'L' : 'M'}${x(d.recall).toFixed(1)},${y(d.precision).toFixed(1)}`).join(''),
    [pts],
  );
  const base = data.fraud_rate;
  const active = hover != null ? pts[hover] : null;

  return (
    <Frame
      title="Precision against recall"
      subtitle={`Every point is an operating point you could run. The dashed rule is the ${pct(base, 2)} base rate — the precision a coin-flip achieves.`}
      readout={
        active ? (
          <span className="fig">
            recall {pct(active.recall, 1)} · precision {pct(active.precision, 1)} · threshold{' '}
            {active.threshold.toFixed(4)}
          </span>
        ) : (
          <span className="text-graphite-400">Hover the curve to read any operating point.</span>
        )
      }
    >
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto" role="img"
           aria-label={`Precision-recall curve, area under curve ${data.pr_auc?.toFixed(3) ?? ''}`}>
        {[0, 0.25, 0.5, 0.75, 1].map((t) => (
          <g key={t}>
            <line x1={P.l} x2={W - P.r} y1={y(t)} y2={y(t)} stroke={GRID} strokeWidth="1" />
            <text x={P.l - 9} y={y(t) + 3.5} textAnchor="end" fontSize="10" fill={MUTED} fontFamily="JetBrains Mono">
              {(t * 100).toFixed(0)}
            </text>
          </g>
        ))}
        {[0, 0.25, 0.5, 0.75, 1].map((t) => (
          <text key={t} x={x(t)} y={H - 18} textAnchor="middle" fontSize="10" fill={MUTED} fontFamily="JetBrains Mono">
            {(t * 100).toFixed(0)}
          </text>
        ))}

        <line x1={P.l} x2={W - P.r} y1={y(base)} y2={y(base)} stroke={FAINT} strokeWidth="1" strokeDasharray="3 3" />
        <text x={W - P.r} y={y(base) - 6} textAnchor="end" fontSize="9.5" fill={MUTED}>
          base rate {pct(base, 2)}
        </text>

        <path ref={drawn.ref} style={drawn.style} className="draw" d={path} fill="none"
              stroke={PRESS} strokeWidth="1.75" strokeLinejoin="round" strokeLinecap="round" />

        {active && (
          <>
            <line x1={x(active.recall)} x2={x(active.recall)} y1={P.t} y2={P.t + ih}
                  stroke={INK} strokeWidth="1" strokeDasharray="2 2" />
            <circle cx={x(active.recall)} cy={y(active.precision)} r="4" fill={PRESS} stroke="#fff" strokeWidth="1.5" />
          </>
        )}
        {pts.map((d, i) => (
          <rect key={i} x={x(d.recall) - iw / pts.length / 2} y={P.t} width={iw / pts.length} height={ih}
                fill="transparent" onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)} />
        ))}

        <line x1={P.l} x2={W - P.r} y1={P.t + ih} y2={P.t + ih} stroke={INK} strokeWidth="1" />
        <text x={P.l + iw / 2} y={H - 4} textAnchor="middle" fontSize="10" fill={MUTED}>recall %</text>
        <text x={13} y={P.t + ih / 2} textAnchor="middle" fontSize="10" fill={MUTED}
              transform={`rotate(-90 13 ${P.t + ih / 2})`}>precision %</text>
      </svg>
    </Frame>
  );
}

/* ========================================================================== */
/* Risk distribution with the policy's boundaries as printed rules            */
/* ========================================================================== */
export function RiskDistribution({ data }: { data: ChartData }) {
  const W = 1180, H = 330, P = { t: 16, r: 18, b: 46, l: 56 };
  const iw = W - P.l - P.r, ih = H - P.t - P.b;
  const [hover, setHover] = useState<number | null>(null);

  const bins = data.distribution.bins;
  const sx = (p: number) => P.l + Math.sqrt(Math.max(0, Math.min(1, p))) * iw;
  const max = Math.max(...bins.map((b) => b.legit + b.fraud), 1);
  const sy = (n: number) => (n / max) * ih;
  const active = hover != null ? bins[hover] : null;

  return (
    <Frame
      title="Where the portfolio sits, and what the policy did with it"
      subtitle="Every held-out transaction by the risk the model assigned. Dashed rules are the policy's action boundaries — the whole argument in one picture."
      right={
        <div className="flex gap-4 note shrink-0">
          <span className="flex items-center gap-2">
            <span className="w-3 h-2 inline-block" style={{ background: INK_2 }} /> clean
          </span>
          <span className="flex items-center gap-2">
            <span className="w-3 h-2 inline-block" style={{ background: LOSS }} /> chargeback
          </span>
        </div>
      }
      readout={
        active ? (
          <span className="fig">
            p {pct(active.from, 1)}–{pct(active.to, 1)} · {count(active.legit)} clean ·{' '}
            <span className="text-loss">{count(active.fraud)} chargeback</span>
          </span>
        ) : (
          <span className="text-graphite-400">Hover a bin for its counts.</span>
        )
      }
    >
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto" role="img"
           aria-label="Distribution of predicted chargeback probability split by outcome, with policy action boundaries">
        {data.policy_bands.slice(1).map((b, i) => (
          <g key={i}>
            <line x1={sx(b.from)} x2={sx(b.from)} y1={P.t} y2={P.t + ih}
                  stroke={INK} strokeWidth="1" strokeDasharray="3 3" />
            <text x={sx(b.from) + 6} y={P.t + 11} fontSize="10" fill={MUTED} fontFamily="JetBrains Mono">
              {b.action.replace('_', '-').toLowerCase()} ≥ {pct(b.from, 1)}
            </text>
          </g>
        ))}

        {bins.map((b, i) => {
          const x0 = sx(b.from), x1 = sx(b.to);
          const w = Math.max(2, x1 - x0 - 3);
          const hL = sy(b.legit), hF = sy(b.fraud);
          const dim = hover != null && hover !== i;
          return (
            <g key={i} opacity={dim ? 0.32 : 1} style={{ transition: 'opacity .15s' }}
               onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)}>
              <rect x={x0} y={P.t + ih - hL} width={w} height={hL} fill={INK_2} />
              <rect x={x0} y={P.t + ih - hL - hF - 1.5} width={w} height={hF} fill={LOSS} />
              <rect x={x0} y={P.t} width={Math.max(w, 5)} height={ih} fill="transparent" />
            </g>
          );
        })}

        <line x1={P.l} x2={W - P.r} y1={P.t + ih} y2={P.t + ih} stroke={INK} strokeWidth="1" />
        {[0, 0.02, 0.1, 0.3, 0.6, 1].map((t) => (
          <text key={t} x={sx(t)} y={H - 24} textAnchor="middle" fontSize="10.5" fill={MUTED} fontFamily="JetBrains Mono">
            {(t * 100).toFixed(t < 0.1 ? 1 : 0)}
          </text>
        ))}
        <text x={P.l + iw / 2} y={H - 6} textAnchor="middle" fontSize="10.5" fill={MUTED}>
          predicted chargeback probability % (√ scale)
        </text>
        <text x={14} y={P.t + ih / 2} textAnchor="middle" fontSize="10.5" fill={MUTED}
              transform={`rotate(-90 14 ${P.t + ih / 2})`}>transactions</text>
      </svg>
    </Frame>
  );
}

/* ========================================================================== */
/* Cost curve — log axis, because one runaway point owns the linear domain     */
/* ========================================================================== */
export function CostCurve({ data }: { data: ChartData }) {
  const W = 620, H = 320, P = { t: 16, r: 16, b: 44, l: 62 };
  const iw = W - P.l - P.r, ih = H - P.t - P.b;
  const [hover, setHover] = useState<number | null>(null);
  const drawn = useDrawn();

  const cc = data.cost_curve;
  const pts = cc.curve;
  const costs = [...pts.map((d) => d.cost_per_1k), cc.policy_cost_per_1k];
  const lo = Math.log10(Math.min(...costs) * 0.9);
  const hi = Math.log10(Math.max(...costs) * 1.1);

  const x = (t: number) => P.l + ((t - pts[0].threshold) / (pts.at(-1)!.threshold - pts[0].threshold)) * iw;
  const y = (c: number) => P.t + (1 - (Math.log10(c) - lo) / (hi - lo)) * ih;
  const path = pts.map((d, i) => `${i ? 'L' : 'M'}${x(d.threshold).toFixed(1)},${y(d.cost_per_1k).toFixed(1)}`).join('');
  const active = hover != null ? pts[hover] : null;

  return (
    <Frame
      title="Cost of every threshold you could pick"
      subtitle="The curve is what a fixed cut-off costs. The solid rule is the cost-optimal policy — it does not sit on the curve, because it is not a threshold."
      readout={
        active ? (
          <span className="fig">
            threshold {active.threshold.toFixed(4)} costs {inr(active.cost_per_1k)} —{' '}
            <span className="text-gain">{inr(active.cost_per_1k - cc.policy_cost_per_1k)} worse than the policy</span>
          </span>
        ) : (
          <span className="text-graphite-400">
            Best threshold {inr(cc.best_threshold_cost_per_1k)}; the policy {inr(cc.policy_cost_per_1k)}.
          </span>
        )
      }
    >
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto" role="img"
           aria-label="Realised cost per 1,000 transactions across fixed thresholds against the cost-optimal policy">
        {[0, 0.25, 0.5, 0.75, 1].map((t) => {
          const c = Math.pow(10, lo + t * (hi - lo));
          return (
            <g key={t}>
              <line x1={P.l} x2={W - P.r} y1={y(c)} y2={y(c)} stroke={GRID} strokeWidth="1" />
              <text x={P.l - 9} y={y(c) + 3.5} textAnchor="end" fontSize="10" fill={MUTED} fontFamily="JetBrains Mono">
                {(c / 1000).toFixed(0)}k
              </text>
            </g>
          );
        })}

        <path ref={drawn.ref} style={drawn.style} className="draw" d={path} fill="none"
              stroke={INK_2} strokeWidth="1.75" strokeLinejoin="round" />

        <circle cx={x(cc.best_threshold)} cy={y(cc.best_threshold_cost_per_1k)} r="3.5" fill="#fff" stroke={INK} strokeWidth="1.5" />
        <text x={x(cc.best_threshold)} y={y(cc.best_threshold_cost_per_1k) - 11} textAnchor="middle" fontSize="9.5" fill={MUTED}>
          best threshold
        </text>

        <line x1={P.l} x2={W - P.r} y1={y(cc.policy_cost_per_1k)} y2={y(cc.policy_cost_per_1k)}
              stroke={GAIN} strokeWidth="1.75" />
        <text x={W - P.r} y={y(cc.policy_cost_per_1k) + 14} textAnchor="end" fontSize="10" fill={GAIN}>
          cost-optimal policy · {inr(cc.policy_cost_per_1k)}
        </text>

        {active && <circle cx={x(active.threshold)} cy={y(active.cost_per_1k)} r="3.5" fill={PRESS} stroke="#fff" strokeWidth="1.5" />}
        {pts.map((d, i) => (
          <rect key={i} x={x(d.threshold) - iw / pts.length / 2} y={P.t} width={iw / pts.length} height={ih}
                fill="transparent" onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)} />
        ))}

        <line x1={P.l} x2={W - P.r} y1={P.t + ih} y2={P.t + ih} stroke={INK} strokeWidth="1" />
        <text x={P.l + iw / 2} y={H - 6} textAnchor="middle" fontSize="10" fill={MUTED}>block threshold</text>
        <text x={14} y={P.t + ih / 2} textAnchor="middle" fontSize="10" fill={MUTED}
              transform={`rotate(-90 14 ${P.t + ih / 2})`}>₹ per 1,000 (log)</text>
      </svg>
    </Frame>
  );
}

/* ========================================================================== */
/* Calibration                                                                */
/* ========================================================================== */
export function CalibrationPlot({
  bins,
}: {
  bins: Array<{ bin: number; n: number; predicted: number; observed: number }>;
}) {
  const W = 380, H = 340, P = { t: 16, r: 18, b: 44, l: 50 };
  const iw = W - P.l - P.r, ih = H - P.t - P.b;
  const [hover, setHover] = useState<number | null>(null);

  const max = Math.max(...bins.flatMap((b) => [b.predicted, b.observed])) * 1.1;
  const x = (v: number) => P.l + (v / max) * iw;
  const y = (v: number) => P.t + (1 - v / max) * ih;
  const maxN = Math.max(...bins.map((b) => b.n));
  const active = hover != null ? bins[hover] : null;

  return (
    <Frame
      title="Calibration"
      subtitle="Predicted against observed, by decile. Points on the diagonal mean a stated probability is the real one — which the rupee arithmetic depends on."
      readout={
        active ? (
          <span className="fig">
            {count(active.n)} txns · predicted {active.predicted.toFixed(4)} · observed{' '}
            {active.observed.toFixed(4)}
          </span>
        ) : (
          <span className="text-graphite-400">Marker size is the number of transactions in the decile.</span>
        )
      }
    >
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto max-w-[22rem] mx-auto block" role="img"
           aria-label="Calibration plot of predicted against observed chargeback rate">
        {[0, 0.5, 1].map((t) => (
          <g key={t}>
            <line x1={P.l} x2={W - P.r} y1={y(max * t)} y2={y(max * t)} stroke={GRID} strokeWidth="1" />
            <text x={P.l - 9} y={y(max * t) + 3.5} textAnchor="end" fontSize="10" fill={MUTED} fontFamily="JetBrains Mono">
              {(max * t).toFixed(2)}
            </text>
            <text x={x(max * t)} y={H - 24} textAnchor="middle" fontSize="10" fill={MUTED} fontFamily="JetBrains Mono">
              {(max * t).toFixed(2)}
            </text>
          </g>
        ))}

        <line x1={x(0)} y1={y(0)} x2={x(max)} y2={y(max)} stroke={FAINT} strokeWidth="1" strokeDasharray="4 3" />
        <text x={x(max) - 4} y={y(max) + 15} textAnchor="end" fontSize="9.5" fill={MUTED}>perfect</text>

        {bins.map((b, i) => (
          <circle
            key={b.bin}
            cx={x(b.predicted)}
            cy={y(b.observed)}
            r={4 + (b.n / maxN) * 7}
            fill={hover === i ? PRESS : 'none'}
            fillOpacity=".18"
            stroke={PRESS}
            strokeWidth="1.5"
            style={{ transition: 'fill .15s' }}
            onMouseEnter={() => setHover(i)}
            onMouseLeave={() => setHover(null)}
          />
        ))}

        <line x1={P.l} x2={W - P.r} y1={P.t + ih} y2={P.t + ih} stroke={INK} strokeWidth="1" />
        <text x={P.l + iw / 2} y={H - 6} textAnchor="middle" fontSize="10" fill={MUTED}>predicted</text>
        <text x={13} y={P.t + ih / 2} textAnchor="middle" fontSize="10" fill={MUTED}
              transform={`rotate(-90 13 ${P.t + ih / 2})`}>observed</text>
      </svg>
    </Frame>
  );
}

/* ========================================================================== */
/* Sensitivity                                                                */
/* ========================================================================== */
export function SensitivityStrip({ data }: { data: ChartData }) {
  const rows = data.sensitivity?.rows ?? [];
  const [hover, setHover] = useState<number | null>(null);
  if (!rows.length) return null;

  const max = Math.max(...rows.map((r) => r.saving_pct));
  const groups = Array.from(new Set(rows.map((r) => r.label)));
  const active = hover != null ? rows[hover] : null;

  return (
    <Frame
      title="Does the conclusion survive its assumptions?"
      subtitle="Every cost in the model is an estimate. Each bar re-runs the whole comparison with one of them moved. A bar at zero would mean the policy loses under that assumption."
      right={
        <span className="fig text-gain text-xs whitespace-nowrap shrink-0">
          {data.sensitivity.wins} / {data.sensitivity.total} favour the policy
        </span>
      }
      readout={
        active ? (
          <span className="fig">
            {active.label} = {active.value} → saves{' '}
            <span className="text-gain">{(active.saving_pct * 100).toFixed(1)}%</span> (
            {inr(active.saving_per_1k_inr)} / 1k)
          </span>
        ) : (
          <span className="text-graphite-400">
            Range {Math.min(...rows.map((r) => r.saving_pct * 100)).toFixed(1)}% –{' '}
            {(max * 100).toFixed(1)}%. Hover any bar for its configuration.
          </span>
        )
      }
    >
      <div className="space-y-4">
        {groups.map((g) => {
          const inGroup = rows.map((r, i) => ({ r, i })).filter(({ r }) => r.label === g);
          return (
            <div key={g}>
              <div className="flex items-baseline justify-between mb-1.5">
                <span className="note">{g}</span>
                <span className="fig text-[.65rem] text-graphite-400">
                  {inGroup.map(({ r }) => r.value).join(' · ')}
                </span>
              </div>
              <div className="flex gap-[3px] items-end h-11 border-b border-graphite-900">
                {inGroup.map(({ r, i }) => (
                  <button
                    key={i}
                    onMouseEnter={() => setHover(i)}
                    onMouseLeave={() => setHover(null)}
                    className="flex-1"
                    style={{
                      height: `${Math.max(8, (r.saving_pct / max) * 100)}%`,
                      background: hover === i ? PRESS : INK_2,
                      transition: 'background .15s, height .7s cubic-bezier(.16,1,.3,1)',
                    }}
                    aria-label={`${g} at ${r.value}: ${(r.saving_pct * 100).toFixed(1)}% saving`}
                  />
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </Frame>
  );
}
