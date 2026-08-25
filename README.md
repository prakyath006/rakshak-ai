# 🛡️ Rakshak AI — AI Chargeback Evidence & Representment Agent

> **Track 02: AI Risk Manager | Razorpay AI Buildathon**  
> *From dispute to defensible evidence, automatically.*

Rakshak AI investigates merchant chargebacks across payment, order, fulfillment, and customer communication data, verifies evidence completeness and consistency against dispute policies, generates a grounded representment package with citation-level traceability, and enforces strict human-approval gates before submission.

---

## 🎯 The Problem

Merchants lose revenue not because disputes are indefensible, but because:
1. **Evidence is fragmented** across logistics, order databases, billing systems, and support emails.
2. **Response deadlines are strict** (missing a response window causes automatic dispute forfeiture).
3. **LLM hallucinations risk account suspension** if ungrounded claims or fake proofs are submitted to card networks.

---

## ⚡ The 6-Stage Autonomous Workflow

Rakshak follows an auditable 6-stage pipeline where the **LLM is never the decision maker**:

```
                    RAZORPAY DISPUTE API / WEBHOOKS
                                  │
                                  ▼
                         ┌─────────────────┐
                         │   1. INGEST     │ (Amount, deadline, reason code)
                         └────────┬────────┘
                                  │
                                  ▼
                         ┌─────────────────┐
                         │   2. CLASSIFY   │ (Deterministic policy lookup)
                         └────────┬────────┘
                                  │
                                  ▼
                         ┌─────────────────┐
                         │ 3. INVESTIGATE  │ (Evidence Graph generation)
                         └────────┬────────┘
                                  │
                                  ▼
                         ┌─────────────────┐
                         │   4. VERIFY     │ (Completeness & Contradictions)
                         └────────┬────────┘
                                  │
                                  ▼
                         ┌─────────────────┐
                         │   5. DECIDE     │ (CONTEST / REVIEW / DO NOT CONTEST)
                         └────────┬────────┘
                                  │
                                  ▼
                         ┌─────────────────┐
                         │   6. ASSEMBLE   │ (Grounded Rebuttal + Citations)
                         └────────┬────────┘
                                  │
                                  ▼
                         ┌─────────────────┐
                         │  HUMAN APPROVAL │ (Irreversible submission gate)
                         └────────┬────────┘
                                  │
                                  ▼
                       PATCH /v1/disputes/:id/contest
```

---

## 📊 20 Golden Cases Benchmark

Rakshak is benchmarked against **20 manually designed ground-truth cases** spanning all 5 dispute categories:

| Category | Reason Codes | Scenarios Covered | Accuracy |
|----------|-------------|-------------------|----------|
| **Goods Not Received** | Visa 13.1, UPI 1064, AmEx C08 | Strong delivery, missing proof, merchant loss, address conflict, partial delivery | **100.0%** |
| **Credit Not Processed** | Visa 13.6, UPI 1061 | Processed refund, promised-unprocessed, partial refund, pending refund | **100.0%** |
| **Not as Described** | Visa 13.3 | Spec match, genuine spec discrepancy, ambiguous listing | **100.0%** |
| **Cancelled Merchandise** | Visa 13.7 | Cancellation after dispatch, pre-dispatch cancellation, policy breach | **100.0%** |
| **Unauthorized / Fraud** | Visa 10.4 | 3DS auth match, international anomaly, identity confirmation, fraud breach | **100.0%** |

---

## 🚀 Quickstart

### Prerequisites
- Python 3.11+
- Node.js 18+

### 1. Run Backend & Evaluation Test Suite
```bash
# Run regression suite across all 20 golden cases
python scripts/evaluate_golden_cases.py

# Start FastAPI server
cd backend
uvicorn app.main:app --reload --port 8000
```

### 2. Run Interactive Dashboard
```bash
cd frontend
npm install
npm run dev
```

Visit `http://localhost:5173` to explore the interactive 3-panel workspace, live evidence graph, and human-approval representment flows.
