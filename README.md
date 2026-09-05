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

## Running it

```bash
# 1. data (needs a Kaggle account + accepting the competition rules)
python -m kaggle competitions download -c ieee-fraud-detection -p data/ieee
cd data/ieee && unzip -o ieee-fraud-detection.zip && cd ../..

# 2. verify the label and the split before trusting anything
python -m ml.inspect_data

# 3. train, calibrate, evaluate
python -m ml.train

# 4. the money layer, sensitivity sweep, and VAMP projection
python -m ml.evaluate_money

# 5. export the scored fold the product serves
python -m ml.export_decisions

# 6. run it
cd backend && uvicorn app.main:app --port 8000
cd frontend && npm install && npm run dev
```

Tests: `python -m pytest ml/ -q` (37 tests covering the cost model, the policy
envelope, the VAMP arithmetic, and the rupee accounting).

### Configuration

Copy `.env.example` to `backend/.env`.

| Variable | Purpose |
|---|---|
| `RAZORPAY_KEY_ID` / `_SECRET` | Test-mode credentials |
| `RAZORPAY_MODE` | `auto` \| `simulated` \| `live`. Ships `simulated`: the test account has no bank-raised disputes, so live contest/accept would 404. Every simulated response is stamped `_simulated: true` and the UI shows an amber badge. |
| `LLM_PROVIDER` / `LLM_MODEL` | `none` for the deterministic path, or `openrouter`. Ships with `minimax/minimax-m3:free`. |

Verify credentials with `python scripts/test_razorpay_keys.py` and
`python scripts/test_llm_key.py --all`.

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
   certainly" and "lose ₹4,00,000 with probability 1%" as equivalent; a merchant does
   not. Risk aversion has to be expressed through the cost inputs.
5. **India is not yet under VAMP.** The fact sheet explicitly states programmes for India will be announced later. The architecture is region-agnostic, but the specific thresholds and fines have not been set for India as of September 2026.
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

## Defence-only

Nothing in this repository generates fraud, probes defences, or evades detection. It
detects, verifies, and responds to losses already incurred.
