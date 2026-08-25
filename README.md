# 🛡️ Rakshak AI (रक्षक AI)
### Autonomous AI Chargeback Evidence & Representment Agent
**Razorpay AI Buildathon — Track 02: AI Risk Manager**

---

## 💡 Executive Summary
When an online merchant receives a chargeback dispute via Razorpay, compiling evidence across orders, payments, logistics, refunds, and support emails typically requires **14 to 20 minutes of manual investigation** per dispute.

**Rakshak AI** transforms this manual burden into an autonomous, evidence-grounded workflow:
1. **Reconstructs the full transaction story** by building an Evidence Graph across internal systems.
2. **Performs 4-Dimensional Verification** (`Completeness`, `Reliability`, `Consistency`, `Relevance`).
3. **Enforces a Hard Safety Invariant**: **0.0% false contests against merchant fault** across all benchmark suites.
4. **Generates Grounded Representment Packages** with 100% atomic claim entailment (`[EV-INV-...]`, `[EV-DEL-...]`).
5. **Requires Verified Human Approval** before irreversible submission to the Razorpay Disputes API.

---

## 📊 Measured Benchmark Performance

### 1. Controlled Held-Out Synthetic Benchmark (1,000 Cases)
> *Evaluated on 1,000 held-out synthetic disputes with hidden ground truth across 5 chargeback categories.*
- **Overall Decision Accuracy**: **97.90%** (979 / 1,000)
- **Contest Recall**: **100.00%** (324 / 324 true contestable cases successfully defended)
- **Contest Precision**: **93.91%** (324 / 345)
- **Unsafe False-Contest Rate (Merchant Fault Violations)**: **0.00%** (0 / 246 breaches)
- **Benchmark Disputed Exposure Classified as Potentially Protectable**: **₹3,972,800.00**

### 2. Adversarial Stress Suite (200 Cases)
> *Targeting cross-order contamination, severe amount mismatches, temporal inversions, and conflicting courier systems.*
- **Adversarial Accuracy**: **83.00%** (166 / 200)
- **Unsafe False-Contest Rate (Merchant Fault)**: **0.00%** (0 / 33 breaches)
- **Over-Aggressive Defense on Ambiguous Traps**: Flagged for human review / analyst inspection rather than risking merchant-fault violations.

### 3. Claim Grounding & Anti-Hallucination Audit (Milestone 4)
- **Total Factual Claims Audited**: **1,631 claims** across 1,000 cases
- **Strictly Entailed Claims**: **1,631 claims**
- **Ungrounded / Hallucinated Claims**: **0 claims**
- **Evidence-Grounded Claim Rate**: **100.00%**

### 4. Operational Time Savings
- **Manual Evidence Preparation Baseline**: **14.4 minutes / case**
- **Rakshak Autonomous Compilation + Human Review**: **35.0 seconds / case**
- **Net Effort Reduction**: **95.9%** (*"Shifts merchant workflow from evidence hunting to evidence verification."*)

---

## 🏛️ System Architecture

```
                         RAZORPAY
                            │
                 ┌──────────┴──────────┐
                 │                     │
      payment.dispute.created        PATCH /v1/disputes/:id/contest
        (HMAC SHA256 Webhook)        (Human-Approved Representment)
                 │                     ▲
                 ▼                     │
        ┌────────────────────────────────────┐
        │       RAKSHAK INGESTION & IDEM     │
        └─────────────────┬──────────────────┘
                          ▼
                 ┌─────────────────┐
                 │   CLASSIFIER    │ (Visa / Mastercard / UPI Reason Codes)
                 └────────┬────────┘
                          ▼
                 ┌─────────────────┐
                 │  INVESTIGATOR   │ (Builds Merkle-Hashed Evidence Graph)
                 └────────┬────────┘
                          ▼
               ┌──────────────────────┐
               │  EVIDENCE GRAPH      │
               │                      │
               │ • Payment Record     │
               │ • Tax Invoice        │
               │ • Carrier Tracking   │
               │ • Support Email Comms│
               │ • Refund Ledger      │
               └──────────┬───────────┘
                          ▼
                ┌─────────────────────┐
                │  4D VERIFICATION    │
                │                     │
                │ • Completeness (40%)│
                │ • Consistency  (30%)│
                │ • Reliability  (15%)│
                │ • Relevance    (15%)│
                └──────────┬──────────┘
                           ▼
                   ┌───────────────┐
                   │ DECISION      │
                   └───────┬───────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
           CONTEST       REVIEW      DON'T CONTEST
              │            │
              ▼            ▼
        ┌─────────────────────────┐
        │  GROUNDED REBUTTAL GEN  │
        └────────────┬────────────┘
                     ▼
             CLAIM ENTAILMENT VERIFIER (100% Grounding)
                     │
                     ▼
             HUMAN APPROVAL GATE (Single-Click Verification)
                     │
                     ▼
             RAZORPAY DISPUTES API ADAPTER
                     │
                     ▼
             AUDIT LOG & PROVENANCE TRAIL
```

---

## 🛠️ Reproduction & Testing Commands

### 1. Verify Regression Suite (20 Golden Cases)
```powershell
python scripts/evaluate_golden_cases.py
```

### 2. Run 1,000-Case Held-Out Statistical Benchmark
```powershell
python scripts/evaluate_unseen_benchmark.py --dataset data/unseen_benchmark_1000.json
```

### 3. Run Benchmark Integrity & Leakage Auditor
```powershell
python scripts/audit_benchmark.py
```

### 4. Run Milestone 4 Claim Grounding & Entailment Audit
```powershell
python scripts/evaluate_grounded_rebuttal.py
```

### 5. Run Measured Empirical Time Savings Benchmark
```powershell
python scripts/evaluate_time_savings.py
```

### 6. Run Complete End-to-End Production Simulation
```powershell
python scripts/test_e2e_production.py
```

---

## 👥 Authors
Built for the **Razorpay AI Buildathon (Track 02: AI Risk Manager)**.
All code and reproduction datasets are open-source and versioned under `v1.0.0-buildathon`.
