# Rakshak

**Acquirer-side chargeback loss prevention — detect, verify, respond.**

Razorpay AI Buildathon · Track 02: AI Risk Manager

---

## The thesis

The brief asks for **"honest metrics including false-positive cost"**. That is a
money question, not an accuracy question, and it is the sentence most submissions
will skim past.

Blocking a good customer costs the basket. Approving a fraudster costs the goods,
the dispute fee, and a contribution to the acquirer's monitoring ratio. Sending a
case to an analyst costs analyst minutes. **These are different amounts of money,
and a model tuned for F1 treats them as identical.**

So Rakshak's output is not a score. It is an *action*, chosen by minimising
expected rupee cost:

```
EC(action | p) = p · cost(action, fraud) + (1 − p) · cost(action, legitimate)
chosen         = argmin over {approve, step-up, review, block}
```

No threshold in this system was hand-tuned. Expected cost is linear in `p`, so the
optimal action is the lower envelope of four straight lines and the boundaries fall
out of the arithmetic (`ml/policy.py::decision_boundaries`).

---

## Headline result

Measured on **88,581 held-out transactions** — the final 31 days of a chronological
split, touched once.

| Strategy | ₹ / 1,000 txns | Fraud through | Good customers blocked |
|---|---:|---:|---:|
| **Cost-optimal policy** | **2,61,397** | **772** | **116** |
| Best fixed threshold | 4,02,767 | 1,812 | 402 |
| Approve everything | 4,96,112 | 3,083 | 0 |
| Review everything | 14,17,892 | 0 | 0 |

**₹1,41,370 saved per 1,000 transactions — 35.1% cheaper than the best baseline.**

The part worth pausing on: the policy is better on **both** error types at once —
57% less fraud through *and* 71% fewer good customers blocked. A single threshold
cannot do that, because it can only trade one error against the other.

### Where the advantage actually comes from

A four-action policy beating a two-action threshold is not obviously a fair fight,
so we measured it (`ml/robustness.py`, section 4):

| | ₹ / 1,000 txns |
|---|---:|
| Tuned threshold (approve/block) | 4,02,767 |
| Same EV policy, **restricted to approve/block** | 4,02,606 |
| EV policy, all four actions | 2,61,397 |

Restricted to two actions the policy lands within **₹161** of the tuned threshold —
0.1% of the gain. **A threshold already is the expected-value-optimal binary rule.**

So essentially all of the 35% comes from having a *middle option* available, not
from the optimiser being clever. That is a narrower claim than "our policy beats
thresholds", and it is the true one: the contribution is recognising that the
uncertain band should be challenged rather than guessed at, and doing the
arithmetic that places its boundaries.

It also explains why no cost assumption flips the conclusion — the policy's action
set strictly contains the threshold's, so it dominates by construction. That is a
structural property, not an empirical discovery, and is reported as such.

The baseline is tuned on the calibration fold, never on test. Tuning a baseline on
the test set makes it an oracle, and beating an oracle you built yourself proves
nothing.

### How solid is that number?

Measured on the same held-out fold (`python -m ml.robustness`):

- **95% bootstrap interval: ₹1,20,946 – ₹1,65,250** per 1,000 transactions
  (400 resamples, 100% of draws positive, SE ₹11,456)
- **Stable across time:** the policy is ahead in **5 of 5 weeks** of the fold, and
  the advantage grows as the fraud rate rises (₹81k in week 1 → ₹264k in the last)
- **No break-even:** sweeping each cost across its full plausible range — with the
  baseline threshold re-tuned at every point — never flips the sign

### The policy wins under every assumption we tested

Every cost above is an estimate, so the conclusion is swept rather than asserted —
**16 of 16 configurations favour the policy**, from +22.6% to +65.7%.

| Assumption swept | Range | Saving range |
|---|---|---|
| Dispute fee | ₹0 – ₹5,000 | 34.6% – 37.9% |
| False-decline cost | 0.5× – 2.5× basket | 22.6% – 48.6% |
| Review cost | ₹100 – ₹1,200 | 35.1% – 35.3% |
| Step-up abandonment | 1% – 20% | 22.8% – 65.7% |

---

## The model

| | |
|---|---|
| **PR-AUC** | **0.5434** vs 0.0348 base rate — **15.6× lift** |
| Brier (calibrated) | 0.0214 |
| ROC-AUC | 0.9045 — *context only, see below* |

**Precision and recall** — the brief's literal words — at cut-offs expressed as
review budgets, because that is how a risk desk actually sets one:

| Operating point | Threshold | Precision | Recall | False positives |
|---|---:|---:|---:|---:|
| 0.5% of traffic | 0.9500 | **95.0%** | 13.7% | 22 |
| 1% of traffic | 0.8770 | 88.7% | 28.4% | 112 |
| 2% of traffic | 0.3915 | 71.3% | 44.4% | 550 |
| Recall 70% | 0.0714 | 26.2% | 69.0% | 5,997 |

ROC-AUC is deliberately *not* the headline. At a 3.48% positive rate the negative
class dominates the false-positive-rate denominator, so ROC-AUC reads near 0.9 for
models that are not much use.

### The data, and why the split is the most important function in the repo

**IEEE-CIS (Vesta)** — 590,540 transactions, 20,663 positive (3.499%). Its `isFraud`
label is defined by Vesta as *"reported chargeback on the card"*, so the target is
literally the outcome this product exists to prevent.

`ml/inspect_data.py` verifies that before anything is trained on it: row count,
positive count, rate band, and observation window all match the documentation.

The split is strictly chronological (`ml/data.py`), and the folds are *asserted*
disjoint rather than assumed. A random split would leak badly here:

- Fraud arrives in rings. Shuffling puts members of the same ring on both sides, so
  the model is scored on cards it has already seen commit fraud.
- Labels are assigned retrospectively over a ~120-day reporting window, so the most
  recent transactions are under-labelled. A time split makes that visible; a random
  split hides it. We report the −1.0% drift rather than tuning around it.
- Deployment is chronological. Any evaluation that shuffles time measures a task
  nobody has.

### Entity resolution — the abuse-ring signal

IEEE-CIS has no user column, but one can be reconstructed. `D1` is days-since-card-
began, so `floor(TransactionDT / 86400) − D1` is approximately constant per account.
Combined with `card1` and `addr1` it yields a latent account identity, and once
transactions are grouped under it, ring behaviour becomes measurable — velocity,
distinct cards touched, spend against the account's own history.

**Six of the top twelve features by gain are these reconstructed-identity features**
(`account_day`, `uid_velocity`, `uid_amt_mean`, `uid_txn_count`, `uid_amt_std`,
`uid_day_span`). They are carrying the model, not decorating it.

**Every encoder is fitted on the training fold only.** Public solutions to this
dataset routinely concatenate train and test before computing frequency encodings.
That scores higher and would be fraud in production, because a training-time feature
would depend on transactions that had not happened yet.

---

## The acquirer angle

Visa's **VAMP** (April 2025, enforced October 2025) monitors merchants *and
acquirers* against dispute-ratio thresholds — and the two tolerances are nothing
alike. Per [Visa's own fact sheet](https://corporate.visa.com/content/dam/VCOM/corporate/visa-perspectives/security-and-trust/documents/visa-acquirer-monitoring-program-fact-sheet-2025.pdf):

| Entity | Threshold | Band |
|---|---:|---|
| **Merchant** (AP/CA/EU/US) | ≥ 220 bps (2.20%) | Excessive |
| **Acquirer** portfolio | ≥ 50 bps (0.50%) | Above Standard |
| **Acquirer** portfolio | ≥ 70 bps (0.70%) | Excessive |

An acquirer is held to a bar roughly **three times tighter** than any single
merchant on its book, measured across every merchant at once. A handful of
merchants running hot drags the whole portfolio toward a band that bills the
acquirer per dispute.

> **India note.** The fact sheet states: *"Programs for Brazil, Chile, and India
> will be announced later."* India is not yet under VAMP as of September 2026.
> However, per-dispute fines at acquirer-level thresholds are the standard Visa
> enforcement pattern globally, and India's programme is expected to follow.
> The architecture is built for that eventuality; the pipeline is region-agnostic.

That asymmetry produces a result merchant-level monitoring cannot see. On the
held-out fold:

| Segment | Own rate | Adds to the book |
|---|---:|---:|
| W | 186 bps | **146.0 bps** |
| C | 1,353 bps | 143.4 bps |
| R | 506 bps | 23.9 bps |

Segment **C** looks seven times worse than **W** by its own rate, yet they
contribute near-identical basis points to the portfolio. **Ranking merchants by
their own dispute rate sends defence effort to the wrong place.**

---

## The model safety envelope

The contest decision is **deterministic**. A chargeback engine that can be argued
into defending a merchant-fault case is worse than no engine, so no model output is
ever an input to the decision rules. The LLM is used at exactly two points, and both
are verified afterwards:

| Stage | What the model does | How it is checked | When it is wrong |
|---|---|---|---|
| **Extraction** (`agents/extractor.py`) | Reads support threads into typed signals | Every signal must cite a **verbatim span**, re-matched against the source | Signal discarded and counted |
| **Drafting** (`agents/rebuttal.py`) | Writes the representment | Every amount, date, identifier and citation must appear in the evidence graph | Draft **rejected wholesale**; template used |

**The safety gate is monotone toward caution.** Surviving signals can move a decision
from `CONTEST` → `REVIEW` and never the reverse, so the blast radius of a
hallucination is bounded *by construction* rather than by prompt wording. The worst a
confidently-wrong model can do is send a winnable case to a human.

Verified live: fed a fabricated quote and a non-existent message ID, the extractor
rejected both and reported 33.3% grounding. Fed a draft containing an invented
tracking number, amount, date and citation, the verifier caught all four.

---

## Architecture

```
razorpay-buildathon/
├── frontend/                  # Vite + React + TypeScript
│   └── src/
│       ├── Landing.tsx        # Marketing site (/) — VAMP thesis, proof, limitations
│       ├── Root.tsx           # Hash router — / → Landing, /#/app → App
│       ├── App.tsx            # App shell — 5 tabs, dispute workspace
│       ├── api.ts             # All fetch calls, typed
│       ├── types.ts           # Shared TypeScript types
│       ├── format.ts          # Currency / number formatting
│       ├── viz/palette.ts     # Validated colour system (contrast + CVD checks)
│       └── components/
│           ├── Header.tsx     # Running-head with system-mode badge
│           ├── Wordmark.tsx   # Brand mark (not a shield)
│           ├── ui.tsx         # Design system — Panel, Head, Stat, Tag, Rule
│           ├── charts/Charts.tsx        # SVG charts: risk distribution, cost curve,
│           │                            # PR curve, calibration, sensitivity strip
│           ├── risk/
│           │   ├── OverviewTab.tsx      # Portfolio hero, cost curve, segments
│           │   ├── QueueTab.tsx         # 88,581 rows ranked by expected loss
│           │   ├── PolicyTab.tsx        # Interactive cost-boundary explorer
│           │   └── EvaluationTab.tsx    # PR curve, calibration, precision/recall table
│           └── workspace/
│               ├── CaseSummaryPanel.tsx
│               ├── DecisionPanel.tsx
│               ├── EvidenceGraphPanel.tsx
│               ├── ExtractionPanel.tsx      # LLM correspondence reading
│               ├── InvestigationSkeleton.tsx # Stage-by-stage loading state
│               ├── RebuttalPanel.tsx
│               ├── VerificationMatrixPanel.tsx
│               ├── AuditTrailPanel.tsx
│               └── ApprovalGatePanel.tsx    # Human approval gate
│
├── backend/                   # FastAPI
│   └── app/
│       ├── config.py          # Settings, loads .env explicitly
│       ├── main.py            # 16 endpoints across /api/risk/*, /api/disputes/*, /api/webhooks/
│       ├── agents/
│       │   ├── decision_engine.py  # Deterministic rules — no model input
│       │   ├── classifier.py       # Risk-score wrapper
│       │   ├── extractor.py        # LLM correspondence reader + verbatim grounding
│       │   ├── investigator.py     # Evidence graph assembly
│       │   ├── pipeline.py         # Orchestrates extract → investigate → decide → draft
│       │   ├── rebuttal.py         # LLM representment drafter + token-level verifier
│       │   └── verifier.py         # Claim-level entailment check
│       └── services/
│           ├── llm.py              # OpenRouter client, retry/backoff, graceful fallback
│           ├── razorpay_adapter.py # Disputes API, simulated/live mode, HMAC webhooks
│           └── risk_store.py       # Serves scored transactions from ML artifacts
│
└── ml/                        # Training and evaluation pipeline
    ├── data.py                # Chronological split with disjoint assertions
    ├── features.py            # Entity resolution + encoders fitted on train only
    ├── train.py               # LightGBM + isotonic calibration
    ├── policy.py              # Cost model, expected-value policy, decision boundaries
    ├── vamp.py                # Acquirer portfolio ratio, VAMP band classification
    ├── money.py               # Realised cost, vectorised; baseline tuning
    ├── evaluate_money.py      # Money table, sensitivity sweep, VAMP projection
    ├── robustness.py          # Bootstrap CI, weekly stability, break-even, attribution
    ├── export_decisions.py    # Writes artifacts/decisions.csv for the risk store
    ├── export_charts.py       # Writes artifacts/charts.json for the frontend charts
    ├── inspect_data.py        # Verifies label definition before training
    ├── test_policy.py         # 27 tests — cost model, policy, VAMP
    └── test_money.py          # 10 tests — realised cost, vectorisation parity
```

### Backend API endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Liveness |
| GET | `/api/system/mode` | Razorpay mode (simulated/live) and LLM status |
| GET | `/api/risk/summary` | Headline money figures for the dashboard |
| GET | `/api/risk/queue` | Scored transactions, paginated, sortable |
| GET | `/api/risk/segments` | Per-segment dispute rates and VAMP contribution |
| GET | `/api/risk/evaluation` | PR-AUC, Brier, precision/recall table |
| GET | `/api/risk/money` | Strategy comparison table |
| GET | `/api/risk/charts` | Pre-computed chart data (distribution, cost curve, etc.) |
| GET | `/api/risk/policy/defaults` | Default cost model parameters |
| POST | `/api/risk/policy/simulate` | Recompute decision boundaries from posted costs |
| GET | `/api/disputes` | List golden test cases |
| GET | `/api/disputes/{id}` | Single case detail |
| POST | `/api/disputes/{id}/investigate` | Run the full LLM pipeline |
| POST | `/api/disputes/{id}/approve-and-submit` | Human-approved contest/accept to Razorpay |
| POST | `/api/webhooks/razorpay` | HMAC-verified webhook ingestion |

### Frontend — five tabs

| Tab | What it shows |
|---|---|
| **Overview** | Hero risk distribution chart, cost curve, segment table, sensitivity sweep |
| **Risk Queue** | All 88,581 scored transactions ranked by expected loss; filter by action band |
| **Policy** | Drag cost sliders — decision boundaries recompute live in the browser |
| **Evaluation** | PR curve, calibration scatter, precision/recall table, feature importance |
| **Disputes** | 20-case regression harness; run full LLM investigation and approve representments |

The landing page (`/`) is a separate document-style site — VAMP thesis, proof, methodology, and limitations — with the app behind "Launch system".

---

## Running it

### Prerequisites

```bash
pip install lightgbm scikit-learn pandas numpy python-dotenv fastapi uvicorn httpx openai
cd frontend && npm install
```

### First run — build the ML artifacts

```bash
# 1. Download data (Kaggle account + accept competition rules at kaggle.com)
kaggle competitions download -c ieee-fraud-detection -p data/ieee
cd data/ieee && unzip -o ieee-fraud-detection.zip && cd ../..

# 2. Verify the label before trusting anything
python -m ml.inspect_data

# 3. Train, calibrate (≈10 min on full 590k rows)
python -m ml.train

# 4. Money evaluation, sensitivity sweep, VAMP projection
python -m ml.evaluate_money

# 5. Robustness: bootstrap CI, weekly stability, break-even, attribution
python -m ml.robustness

# 6. Export scored fold and chart data for the product
python -m ml.export_decisions
python -m ml.export_charts
```

### Start the app

```bash
# Terminal 1 — backend
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# Terminal 2 — frontend
cd frontend
npm run dev
# Open http://127.0.0.1:5173
```

### Refresh demo deadlines (before recording a demo)

```bash
python scripts/refresh_demo_deadlines.py
# Spreads fixture deadlines across critical / high / normal tiers
```

### Tests

```bash
python -m pytest ml/ -q          # 37 tests — cost model, policy, VAMP, money
python scripts/evaluate_golden_cases.py   # 20/20 regression harness
python scripts/test_e2e_production.py     # 7 end-to-end scenarios
```

### Verify credentials

```bash
python scripts/test_razorpay_keys.py   # auth, disputes endpoint, creates a live order
python scripts/test_llm_key.py --all   # auth + real completion, lists model slugs
```

### Configuration

Copy `.env.example` to `backend/.env`:

| Variable | Purpose |
|---|---|
| `RAZORPAY_KEY_ID` / `_SECRET` | Test-mode credentials |
| `RAZORPAY_MODE` | `auto` \| `simulated` \| `live`. Ships `simulated` — the test account has no bank-raised disputes, so live contest/accept would 404. Every simulated response is stamped `_simulated: true` and the UI shows an amber badge. |
| `LLM_PROVIDER` | `none` for the deterministic path, or `openrouter`. |
| `LLM_MODEL` | Model slug on OpenRouter. Ships `minimax/minimax-m3:free`. Swap to a paid model (e.g. `anthropic/claude-sonnet-4-5`) for faster demo latency. |
| `OPENROUTER_API_KEY` | Required when `LLM_PROVIDER=openrouter`. |

---

## Honest limitations

Stated here because "honest metrics" is a scored criterion, not a disclaimer.

1. **IEEE-CIS is US card-not-present e-commerce, not Indian UPI.** The pipeline and
   the decision layer generalise; the weights do not. The model retrains on a
   merchant's own history, which is how these systems actually ship. We are not
   claiming Indian coverage we do not have.
2. **This fold is 3.48% fraudulent — not a representative portfolio rate.** IEEE-CIS
   is enriched traffic. The absolute VAMP band labels are therefore inflated and are
   *not* a claim about any real book. The transferable figure is the **57.4% relative
   dispute reduction**, which is scale-free.
3. **Every cost is an assumption.** Nobody measured ₹850 or a 4.5% abandonment rate
   for a specific merchant. The sensitivity sweep is the mitigation and ships with
   the headline, not after it.
4. **Expected value is risk-neutral by construction.** It treats "lose ₹4,000
   certainly" and "lose ₹4,00,000 with probability 1%\" as equivalent; a merchant does
   not. Risk aversion has to be expressed through the cost inputs.
5. **India is not yet under VAMP.** The fact sheet explicitly states programmes for
   India will be announced later. The architecture is region-agnostic, but the
   specific thresholds and fines have not been set for India as of September 2026.
6. **Selective labelling is not handled.** In production a blocked transaction
   never produces an outcome, so a deployed system's training data is contaminated
   by its own past decisions and goes blind exactly where it acts. Real teams use
   holdout traffic, propensity weighting or deliberate exploration. IEEE-CIS hides
   the problem because every transaction in it was approved. This is the first thing
   that would need solving before any live deployment.
7. **The dispute-agent half evaluates differently.** Its 20-case golden suite is a
   hand-written regression harness that catches breakage, not a measurement. An
   earlier synthetic 1,000-case benchmark was retired from this README because it was
   partly circular: rules matched phrasing the generator produced.
8. **LLM response latency is 8–15 seconds per investigation.** The free-tier model
   (`minimax/minimax-m3:free`) makes two sequential round-trips. Swap `LLM_MODEL` to
   a paid model for demo use. The deterministic path is unaffected (`LLM_PROVIDER=none`).

---

## Defence-only

Nothing in this repository generates fraud, probes defences, or evades detection. It
detects, verifies, and responds to losses already incurred.
