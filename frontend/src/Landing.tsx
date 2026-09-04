import { useEffect, useRef, useState } from 'react';
import * as api from './api';
import type { ChartData, MoneyReport, RiskStatus, RiskSummary } from './types';
import { count, inr, pct } from './format';
import { Wordmark } from './components/Wordmark';

/* ==========================================================================
 * The site is set as a document, not a landing page.
 *
 * A chargeback fight is a paperwork fight — reason codes, evidence bundles,
 * representments, response deadlines. So the page borrows the conventions of the
 * thing it is about: a masthead, ruled tables, figures set large and tabular,
 * numbered notes instead of tooltips, and a colophon. There are no cards, no
 * gradients, no glow, and the only ornament is a hairline rule.
 * ========================================================================== */

function useReveal<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      el.classList.add('shown');
      return;
    }
    const io = new IntersectionObserver(
      ([e]) => e.isIntersecting && (el.classList.add('shown'), io.disconnect()),
      { rootMargin: '0px 0px -10% 0px' },
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);
  return ref;
}

/** Counts to a figure once it is on screen. Figures are the content here. */
function Figure({
  value,
  format,
  className = '',
}: {
  value: number | undefined;
  format: (n: number) => string;
  className?: string;
}) {
  const ref = useRef<HTMLSpanElement>(null);
  const [shown, setShown] = useState(0);

  useEffect(() => {
    if (value == null) return;
    const el = ref.current;
    if (!el) return;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      setShown(value);
      return;
    }
    const io = new IntersectionObserver(([e]) => {
      if (!e.isIntersecting) return;
      io.disconnect();
      const start = performance.now();
      const tick = (now: number) => {
        const t = Math.min(1, (now - start) / 1100);
        setShown(value * (1 - Math.pow(1 - t, 4)));
        if (t < 1) requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
    });
    io.observe(el);
    return () => io.disconnect();
  }, [value]);

  return (
    <span ref={ref} className={`fig ${className}`}>
      {value == null ? '—' : format(shown)}
    </span>
  );
}

function Rule({ heavy = false, soft = false }: { heavy?: boolean; soft?: boolean }) {
  return <div className={heavy ? 'hr-heavy' : soft ? 'hr-soft' : 'hr'} />;
}

function Block({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  const ref = useReveal<HTMLDivElement>();
  return (
    <div ref={ref} data-reveal className={className}>
      {children}
    </div>
  );
}

/** Section number + title, set like a document's running head. */
function Head({ n, children }: { n: string; children: React.ReactNode }) {
  return (
    <div className="flex items-baseline gap-4 mb-8">
      <span className="fig text-graphite-400 text-sm shrink-0">{n}</span>
      <h2 className="font-display text-[clamp(1.5rem,3vw,2.1rem)] leading-tight tracking-[-.01em]">
        {children}
      </h2>
    </div>
  );
}

export default function Landing({ onLaunch }: { onLaunch: () => void }) {
  const [summary, setSummary] = useState<RiskSummary | null>(null);
  const [status, setStatus] = useState<RiskStatus | null>(null);
  const [money, setMoney] = useState<MoneyReport | null>(null);
  const [charts, setCharts] = useState<ChartData | null>(null);

  useEffect(() => {
    Promise.all([api.fetchRiskSummary(), api.fetchRiskStatus(), api.fetchMoney(), api.fetchCharts()])
      .then(([su, st, mo, ch]) => {
        setSummary(su);
        setStatus(st);
        setMoney(mo);
        setCharts(ch.available ? ch : null);
      })
      .catch(() => undefined);
  }, []);

  const policy = money?.strategies?.find((s) => s.name === 'cost-optimal policy');
  const baseline = money?.strategies?.find((s) => s.name === money?.best_baseline);
  const dist = charts?.distribution.bins;

  return (
    <div className="doc min-h-screen font-sans antialiased">
      {/* ============================================================ masthead */}
      <header className="border-b-2 border-graphite-900">
        <div className="max-w-[76rem] mx-auto px-6">
          <div className="flex items-center justify-between gap-6 py-4">
            <Wordmark className="text-[1.05rem]" sub="Track 02" />
            <button
              onClick={onLaunch}
              className="font-mono text-2xs tracking-[.1em] uppercase border border-graphite-900 px-3.5 py-2 hover:bg-graphite-900 hover:text-paper transition-colors"
            >
              Open the system →
            </button>
          </div>
        </div>
      </header>

      {/* running head: the document's own metadata, like a report's title block */}
      <div className="border-b border-paper-rule">
        <div className="max-w-[76rem] mx-auto px-6 py-2.5 flex flex-wrap gap-x-8 gap-y-1 note">
          <span>Acquirer-side chargeback loss prevention</span>
          <span className="text-graphite-400">·</span>
          <span>Detect · Verify · Respond</span>
          <span className="text-graphite-400">·</span>
          <span>Evaluated on {count(status?.rows_test || 88581)} held-out transactions</span>
          <span className="text-graphite-400">·</span>
          <span>Defence-only</span>
        </div>
      </div>

      {/* ============================================================== lede */}
      <section className="max-w-[76rem] mx-auto px-6 pt-16 sm:pt-24 pb-16">
        <div className="grid lg:grid-cols-12 gap-x-10 gap-y-10">
          <div className="lg:col-span-7">
            <h1 className="font-display font-normal text-[clamp(2.4rem,5.4vw,4.2rem)] leading-[1.02] tracking-[-.02em] text-balance">
              A risk system&rsquo;s output is not a score.
              <br />
              It is an action, and every action
              <br />
              has a price.
            </h1>

            <p className="mt-8 text-[1.02rem] leading-[1.7] text-graphite-700 max-w-[38rem]">
              Blocking a good customer costs the basket. Approving a fraudster costs the goods, the
              dispute fee, and a step toward a monitoring threshold. Sending a case to an analyst
              costs analyst minutes. A model tuned for F<span className="align-sub text-[.7em]">1</span>{' '}
              treats those as the same thing. This one prices them and picks the cheapest defensible
              action.
            </p>
          </div>

          {/* the headline figure, set like a financial statement's key number */}
          <div className="lg:col-span-5 lg:pl-10 lg:border-l lg:border-paper-rule">
            <div className="smallcaps text-graphite-500 text-xs mb-3">
              Saved per 1,000 transactions
            </div>
            <div className="text-[clamp(2.6rem,6vw,3.9rem)] leading-none text-press">
              <Figure value={summary?.saving_per_1k_inr} format={(n) => inr(n)} />
            </div>
            <div className="mt-4 note leading-relaxed">
              against the best fixed threshold we could tune — tuned on its own fold, never on the
              test set. {summary?.saving_pct != null && `${pct(summary.saving_pct)} cheaper.`}
            </div>
            <div className="mt-2 note">
              95% bootstrap interval{' '}
              <span className="fig text-graphite-900">₹1,20,946 – ₹1,65,250</span>; ahead in all five
              weeks of the fold.
            </div>

            <div className="mt-8 space-y-0">
              <Rule />
              {[
                ['Held-out transactions', count(status?.rows_test || 0)],
                ['Fraud let through', policy ? count(policy.fraud_approved) : '—'],
                ['Good customers blocked', policy ? count(policy.legit_blocked) : '—'],
                ['PR-AUC', status?.pr_auc ? status.pr_auc.toFixed(4) : '—'],
              ].map(([k, v]) => (
                <div key={k}>
                  <div className="flex items-baseline justify-between gap-4 py-2.5">
                    <span className="text-sm text-graphite-700">{k}</span>
                    <span className="fig text-sm">{v}</span>
                  </div>
                  <Rule soft />
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* =========================================================== §1 */}
      <section className="max-w-[76rem] mx-auto px-6 py-16">
        <Rule heavy />
        <div className="pt-10">
          <Block>
            <Head n="§1">The asymmetry nobody prices</Head>

            <div className="grid lg:grid-cols-12 gap-x-10 gap-y-8">
              <div className="lg:col-span-5">
                <p className="text-[.98rem] leading-[1.7] text-graphite-700">
                  Under Visa&rsquo;s Acquirer Monitoring Programme, a merchant is flagged
                  &ldquo;excessive&rdquo; at a dispute ratio several times looser than the one an
                  acquirer is held to — and the acquirer&rsquo;s is measured across every merchant on
                  its book at once.
                </p>
                <p className="mt-4 text-[.98rem] leading-[1.7] text-graphite-700">
                  So a handful of merchants running hot do not merely hurt themselves. They drag the
                  whole portfolio toward a band that bills the acquirer per dispute.
                  <sup className="fig text-press text-[.7em] ml-0.5">1</sup>
                </p>
              </div>

              {/* a ruled table, typeset — not a card */}
              <div className="lg:col-span-7">
                <table className="w-full">
                  <caption className="text-left smallcaps text-graphite-500 text-xs pb-3">
                    Dispute-ratio thresholds
                  </caption>
                  <tbody>
                    {[
                      { who: 'Merchant', v: '2.2%', w: 100, note: 'flagged excessive' },
                      { who: 'Acquirer — Razorpay’s role', v: '≈0.3%', w: 13.6, note: 'portfolio-wide' },
                    ].map((r, i) => (
                      <tr key={r.who} className={i === 0 ? 'border-y border-graphite-900' : 'border-b border-paper-rule'}>
                        <th scope="row" className="text-left font-normal py-4 pr-4 align-top">
                          <div className="text-[.95rem]">{r.who}</div>
                          <div className="note mt-0.5">{r.note}</div>
                        </th>
                        <td className="py-4 w-1/2 align-middle">
                          <div className="h-[3px] bg-paper-sunk">
                            <div
                              className={i === 0 ? 'h-full bg-graphite-300' : 'h-full bg-loss'}
                              style={{ width: `${r.w}%` }}
                            />
                          </div>
                        </td>
                        <td className="py-4 pl-4 text-right align-middle">
                          <span className="fig text-[1.35rem]">{r.v}</span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>

                <p className="note mt-5 leading-relaxed border-l-2 border-press pl-4">
                  Which means ranking merchants by their own dispute rate points defence effort at
                  the wrong ones. On our held-out fold the segment that looks seven times worse by
                  its own rate contributes <em>fewer</em> basis points to the book than one that
                  looks healthy.
                </p>
              </div>
            </div>
          </Block>
        </div>
      </section>

      {/* =========================================================== §2 */}
      <section className="max-w-[76rem] mx-auto px-6 py-16">
        <Rule heavy />
        <div className="pt-10">
          <Block>
            <Head n="§2">No threshold here was tuned</Head>

            <div className="grid lg:grid-cols-12 gap-x-10 gap-y-8">
              <div className="lg:col-span-5">
                <p className="text-[.98rem] leading-[1.7] text-graphite-700">
                  Expected cost is linear in the fraud probability, so the optimal action is the
                  lower envelope of four straight lines. The boundaries are solved, not chosen — and
                  each one can be explained to a merchant in a sentence about money.
                </p>
              </div>

              <div className="lg:col-span-7">
                <div className="bg-paper-raised border border-paper-rule px-6 py-6 overflow-x-auto">
                  <div className="fig text-[.9rem] leading-[2]">
                    <div>
                      EC(<span className="text-press">a</span> | p) = p · cost(
                      <span className="text-press">a</span>, fraud) + (1 − p) · cost(
                      <span className="text-press">a</span>, legitimate)
                    </div>
                    <div>
                      chosen = <span className="text-gain">argmin</span>
                      <sub className="text-[.75em]">a</sub> EC(<span className="text-press">a</span> | p)
                    </div>
                  </div>
                </div>

                <table className="w-full mt-6">
                  <tbody>
                    {[
                      ['Approve', 'Nothing if clean. The goods, the fee and the ratio if not.'],
                      ['Step-up auth', 'Cheap friction. Stops most fraud, loses a few good customers.'],
                      ['Manual review', 'Analyst minutes, and an analyst right about 92% of the time.'],
                      ['Block', 'Free against fraud. The whole basket against a good customer.'],
                    ].map(([k, v]) => (
                      <tr key={k} className="border-b border-paper-rule-soft">
                        <th scope="row" className="text-left font-medium text-[.9rem] py-3 pr-6 w-40 align-top">
                          {k}
                        </th>
                        <td className="py-3 text-[.9rem] text-graphite-700 leading-relaxed">{v}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </Block>
        </div>
      </section>

      {/* =========================================================== §3 */}
      <section className="max-w-[76rem] mx-auto px-6 py-16">
        <Rule heavy />
        <div className="pt-10">
          <Block>
            <Head n="§3">Better on both errors at once</Head>

            <p className="text-[.98rem] leading-[1.7] text-graphite-700 max-w-[42rem] mb-6">
              A single threshold can only trade one error against the other. Pricing each action lets
              the policy use step-up authentication across the uncertain middle — so it lets less
              fraud through <em>and</em> blocks fewer good customers than the best threshold.
            </p>

            {/* A four-action policy beating a two-action threshold is not obviously
                a fair fight. Saying where the gain comes from is a narrower claim
                than the headline, and the true one. */}
            <p className="note leading-relaxed border-l-2 border-press pl-4 max-w-[46rem] mb-10">
              <strong className="text-graphite-900">Where that comes from, precisely.</strong> Run
              the same expected-value rule restricted to approve/block and it lands within{' '}
              <strong className="text-graphite-900">₹161</strong> of the tuned threshold — 0.1% of
              the gain. A threshold already <em>is</em> the expected-value-optimal binary rule. So
              essentially all of the advantage is having a middle option at all, with the arithmetic
              placing its boundaries — not the optimiser being clever.
            </p>

            {money?.strategies && (
              <table className="w-full">
                <caption className="text-left smallcaps text-graphite-500 text-xs pb-3">
                  Realised cost on the held-out fold, per 1,000 transactions
                </caption>
                <thead>
                  <tr className="border-y border-graphite-900">
                    <th className="text-left font-medium text-xs smallcaps py-2.5">Strategy</th>
                    <th className="text-right font-medium text-xs smallcaps py-2.5">Cost</th>
                    <th className="text-right font-medium text-xs smallcaps py-2.5">Fraud through</th>
                    <th className="text-right font-medium text-xs smallcaps py-2.5">Good blocked</th>
                  </tr>
                </thead>
                <tbody>
                  {money.strategies.map((s) => {
                    const isPolicy = s.name === 'cost-optimal policy';
                    return (
                      <tr key={s.name} className="border-b border-paper-rule-soft">
                        <td className={`py-3 text-[.92rem] ${isPolicy ? 'font-semibold' : 'text-graphite-700'}`}>
                          {isPolicy && <span className="text-press mr-1.5">▸</span>}
                          {s.name}
                        </td>
                        <td className={`py-3 text-right fig text-[.92rem] ${isPolicy ? 'text-press font-semibold' : ''}`}>
                          {inr(s.cost_per_1k_inr)}
                        </td>
                        <td className="py-3 text-right fig text-[.92rem] text-graphite-700">
                          {count(s.fraud_approved)}
                        </td>
                        <td className="py-3 text-right fig text-[.92rem] text-graphite-700">
                          {count(s.legit_blocked)}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}

            {policy && baseline && (
              <div className="grid sm:grid-cols-3 gap-px bg-paper-rule mt-10 border border-paper-rule">
                {[
                  ['Cheaper', pct(summary?.saving_pct || 0)],
                  ['Less fraud through', pct(1 - policy.fraud_approved / baseline.fraud_approved)],
                  ['Fewer good customers blocked', pct(1 - policy.legit_blocked / baseline.legit_blocked)],
                ].map(([k, v]) => (
                  <div key={k} className="bg-paper px-5 py-6">
                    <div className="fig text-[2rem] leading-none text-gain">{v}</div>
                    <div className="note mt-2.5">{k}</div>
                  </div>
                ))}
              </div>
            )}

            {/* the distribution, drawn as line art on paper */}
            {dist && charts && (
              <div className="mt-12">
                <div className="smallcaps text-graphite-500 text-xs mb-4">
                  Where the portfolio sits — every held-out transaction by assigned risk
                </div>
                <PaperDistribution charts={charts} />
              </div>
            )}

            {charts?.sensitivity && (
              <p className="note mt-8 leading-relaxed border-l-2 border-press pl-4 max-w-[46rem]">
                Every cost above is an estimate, so each was swept:{' '}
                <strong className="text-graphite-900">
                  {charts.sensitivity.wins} of {charts.sensitivity.total} configurations favour the
                  policy
                </strong>
                , from {Math.min(...charts.sensitivity.rows.map((r) => r.saving_pct * 100)).toFixed(1)}% to{' '}
                {Math.max(...charts.sensitivity.rows.map((r) => r.saving_pct * 100)).toFixed(1)}%.
                <sup className="fig text-press text-[.9em] ml-0.5">2</sup>
              </p>
            )}
          </Block>
        </div>
      </section>

      {/* =========================================================== §4 */}
      <section className="max-w-[76rem] mx-auto px-6 py-16">
        <Rule heavy />
        <div className="pt-10">
          <Block>
            <Head n="§4">The model may only assert what it can quote</Head>

            <p className="text-[.98rem] leading-[1.7] text-graphite-700 max-w-[42rem] mb-10">
              The contest decision is deterministic — no model output is ever an input to it. The
              language model reads support threads and drafts representments, and both are checked
              against the evidence afterwards.
            </p>

            <div className="grid md:grid-cols-3 gap-px bg-paper-rule border border-paper-rule">
              {[
                ['Verbatim quote grounding', 'Every extracted signal must cite a span re-matched against the source message. Fed a fabricated quote, it rejected it and reported 33% grounding.'],
                ['Token-level draft checks', 'Every amount, date, identifier and citation in a drafted representment must appear in the evidence graph, or the draft is discarded whole.'],
                ['A gate that moves one way', 'Signals may move a decision toward review, never away. The blast radius of a hallucination is bounded by construction, not by prompt wording.'],
              ].map(([t, d], i) => (
                <div key={t} className="bg-paper px-6 py-7">
                  <div className="fig text-graphite-400 text-xs mb-3">{String(i + 1).padStart(2, '0')}</div>
                  <div className="font-display text-[1.05rem] leading-snug mb-2.5">{t}</div>
                  <p className="note leading-relaxed">{d}</p>
                </div>
              ))}
            </div>
          </Block>
        </div>
      </section>

      {/* =========================================================== notes */}
      <section className="max-w-[76rem] mx-auto px-6 py-16">
        <Rule heavy />
        <div className="pt-10">
          <Block>
            <Head n="§5">What this does not prove</Head>
            <p className="text-[.98rem] leading-[1.7] text-graphite-700 max-w-[42rem] mb-8">
              The brief asks for honest metrics. That is a scored criterion rather than a disclaimer,
              so the weak points belong in the body of the document, not an appendix.
            </p>

            <ol className="space-y-0 max-w-[52rem]">
              {[
                ['IEEE-CIS is US card-not-present traffic, not Indian UPI.', 'The pipeline and the decision layer generalise; the weights do not. The model retrains on a merchant’s own history, which is how these systems actually ship.'],
                ['This fold is 3.48% fraudulent — not a portfolio rate.', 'It is enriched data. Absolute monitoring bands are therefore inflated; the transferable figure is the 57% relative reduction in disputes.'],
                ['Every cost is an assumption.', 'Nobody measured ₹850 for a specific merchant. The sensitivity sweep ships with the headline rather than after it.'],
                ['Expected value is risk-neutral by construction.', 'It treats a certain ₹4,000 loss and a 1% chance of ₹4,00,000 as equivalent. A merchant does not. Risk aversion has to enter through the cost inputs.'],
                ['The monitoring thresholds are not yet verified at source.', 'They come from secondary reporting that disagrees on the acquirer bands, and are marked unverified in the code until read from the scheme’s own document.'],
                ['Selective labelling is not handled.', 'A blocked transaction never produces an outcome, so a deployed system’s training data is contaminated by its own past decisions and goes blind where it acts. IEEE-CIS hides this because every transaction in it was approved. It is the first thing that would need solving before a live deployment.'],
              ].map(([t, d], i) => (
                <li key={t}>
                  <Rule soft />
                  <div className="flex gap-5 py-4">
                    <span className="fig text-press text-sm shrink-0 pt-0.5">{i + 1}</span>
                    <div>
                      <div className="text-[.95rem] font-medium">{t}</div>
                      <p className="note mt-1.5 leading-relaxed">{d}</p>
                    </div>
                  </div>
                </li>
              ))}
            </ol>
          </Block>
        </div>
      </section>

      {/* =========================================================== colophon */}
      <section className="max-w-[76rem] mx-auto px-6 pb-20">
        <Rule heavy />
        <div className="pt-12 pb-6 flex flex-col sm:flex-row sm:items-end justify-between gap-8">
          <div>
            <div className="font-display text-[clamp(1.5rem,3vw,2.1rem)] leading-tight max-w-[26rem] text-balance">
              Everything above is live in the system.
            </div>
            <p className="note mt-3 max-w-[30rem] leading-relaxed">
              Drag the cost assumptions and watch the boundaries re-derive. Page through{' '}
              {count(status?.rows_test || 88581)} scored transactions. Read the precision, recall and
              calibration off the held-out fold.
            </p>
          </div>
          <button
            onClick={onLaunch}
            className="shrink-0 font-mono text-2xs tracking-[.1em] uppercase border-2 border-graphite-900 px-6 py-3.5 hover:bg-graphite-900 hover:text-paper transition-colors"
          >
            Open the system →
          </button>
        </div>

        <Rule />
        <div className="py-6 flex flex-wrap gap-x-8 gap-y-2 note">
          <span>Rakshak</span>
          <span className="text-graphite-400">·</span>
          <span>Razorpay AI Buildathon, Track 02 — AI Risk Manager</span>
          <span className="text-graphite-400">·</span>
          <span>
            Data: IEEE-CIS (Vesta), 590,540 transactions, label = reported chargeback on the card
          </span>
          <span className="text-graphite-400">·</span>
          <span>Strictly defence-only</span>
        </div>
      </section>
    </div>
  );
}

/* --------------------------------------------------------------------------
 * The distribution, redrawn for paper.
 *
 * The app's version is built for a dark ground with fills and glow. On paper the
 * same data wants line art: hairline bars, a printed rule for each boundary, and
 * ink for the marks rather than colour-as-decoration.
 * ------------------------------------------------------------------------ */
function PaperDistribution({ charts }: { charts: ChartData }) {
  const bins = charts.distribution.bins;
  const W = 1180, H = 300, P = { t: 14, r: 16, b: 42, l: 52 };
  const iw = W - P.l - P.r, ih = H - P.t - P.b;
  const [hover, setHover] = useState<number | null>(null);

  const sx = (p: number) => P.l + Math.sqrt(Math.max(0, Math.min(1, p))) * iw;
  const max = Math.max(...bins.map((b) => b.legit + b.fraud), 1);
  const sy = (n: number) => (n / max) * ih;
  const active = hover != null ? bins[hover] : null;

  return (
    <div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto" role="img"
           aria-label="Distribution of predicted chargeback probability, split by outcome, with the policy's action boundaries">
        {/* boundaries as printed rules, labelled — no colour fills */}
        {charts.policy_bands.slice(1).map((b, i) => (
          <g key={i}>
            <line x1={sx(b.from)} x2={sx(b.from)} y1={P.t} y2={P.t + ih}
                  stroke="#0f1319" strokeWidth="1" strokeDasharray="3 3" />
            <text x={sx(b.from) + 5} y={P.t + 11} fontSize="10" fill="#5a6675" fontFamily="JetBrains Mono">
              {b.action.replace('_', '-').toLowerCase()} ≥ {(b.from * 100).toFixed(1)}%
            </text>
          </g>
        ))}

        <line x1={P.l} x2={W - P.r} y1={P.t + ih} y2={P.t + ih} stroke="#0f1319" strokeWidth="1" />

        {bins.map((b, i) => {
          const x0 = sx(b.from), x1 = sx(b.to);
          const w = Math.max(2, x1 - x0 - 3);
          const hL = sy(b.legit), hF = sy(b.fraud);
          const dim = hover != null && hover !== i;
          return (
            <g key={i} opacity={dim ? 0.35 : 1} style={{ transition: 'opacity .15s' }}
               onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)}>
              <rect x={x0} y={P.t + ih - hL} width={w} height={hL} fill="#2c3540" />
              <rect x={x0} y={P.t + ih - hL - hF - 1.5} width={w} height={hF} fill="#a6303c" />
              <rect x={x0} y={P.t} width={Math.max(w, 5)} height={ih} fill="transparent" />
            </g>
          );
        })}

        {[0, 0.02, 0.1, 0.3, 0.6, 1].map((t) => (
          <text key={t} x={sx(t)} y={H - 22} textAnchor="middle" fontSize="10.5" fill="#5a6675" fontFamily="JetBrains Mono">
            {(t * 100).toFixed(t < 0.1 ? 1 : 0)}%
          </text>
        ))}
        <text x={P.l + iw / 2} y={H - 5} textAnchor="middle" fontSize="10.5" fill="#5a6675">
          predicted chargeback probability (√ scale)
        </text>
        <text x={14} y={P.t + ih / 2} textAnchor="middle" fontSize="10.5" fill="#5a6675"
              transform={`rotate(-90 14 ${P.t + ih / 2})`}>transactions</text>
      </svg>

      <div className="flex items-center justify-between gap-4 mt-2 note min-h-[1.5rem]">
        <span className="flex gap-5">
          <span className="flex items-center gap-2">
            <span className="w-3 h-2 inline-block" style={{ background: '#2c3540' }} /> clean
          </span>
          <span className="flex items-center gap-2">
            <span className="w-3 h-2 inline-block" style={{ background: '#a6303c' }} /> chargeback
          </span>
        </span>
        {active && (
          <span className="fig">
            p {(active.from * 100).toFixed(1)}–{(active.to * 100).toFixed(1)}% · {count(active.legit)} clean ·{' '}
            <span className="text-loss">{count(active.fraud)} chargeback</span>
          </span>
        )}
      </div>
    </div>
  );
}
