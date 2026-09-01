"""Export the scored held-out fold as the decision log the product serves.

    python -m ml.export_decisions

The application does not re-run the model on every request. It serves this
export: 88,581 real transactions from the final 31 days, each carrying the
calibrated probability the model assigned and the action the cost policy chose.

Everything in the UI therefore traces back to a real held-out prediction. There
is no synthetic queue anywhere in the product.

A note on "merchant": IEEE-CIS has no merchant column — it is a single payment
processor's traffic. `ProductCD` (the product category) is used as the portfolio
segment instead, and is labelled as a segment in the UI rather than being passed
off as a merchant. The portfolio arithmetic is identical; only the noun changes.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from ml.data import AMOUNT, ID, LABEL, TIME, load_raw, time_split
from ml.money import USD_INR, cost_optimal
from ml.policy import CostModel

ARTIFACT_DIR = Path(__file__).resolve().parent.parent / "artifacts"

DISPLAY_COLUMNS = [
    ID, TIME, AMOUNT, LABEL,
    "ProductCD", "card4", "card6", "P_emaildomain", "DeviceType", "addr1",
]


def main() -> int:
    p_test = np.load(ARTIFACT_DIR / "test_p.npy")

    print("Reloading the held-out fold (the split is deterministic, so it realigns) ...")
    df = load_raw()
    split = time_split(df)
    test = split.test.reset_index(drop=True)

    if len(test) != len(p_test):
        raise SystemExit(
            f"Fold size {len(test):,} does not match saved predictions {len(p_test):,}. "
            "Re-run `python -m ml.train` so the artifacts agree."
        )

    costs = CostModel()
    amounts_inr = test[AMOUNT].to_numpy() * USD_INR
    actions = cost_optimal(p_test, amounts_inr, costs)

    out = test[[c for c in DISPLAY_COLUMNS if c in test.columns]].copy()
    out["p_fraud"] = p_test
    out["amount_inr"] = amounts_inr
    out["action"] = actions
    out["expected_loss_inr"] = p_test * (amounts_inr + costs.dispute_fee)

    # Day index within the fold, so the UI can show a real timeline without
    # inventing wall-clock dates the dataset deliberately withholds.
    out["day"] = ((test[TIME] - test[TIME].min()) // 86_400).astype(int)

    out = out.sort_values("expected_loss_inr", ascending=False).reset_index(drop=True)

    path = ARTIFACT_DIR / "decisions.csv"
    out.to_csv(path, index=False)
    print(f"Wrote {len(out):,} scored decisions -> {path}")

    # Portfolio segments, precomputed so the API does no aggregation at request time.
    seg = (
        out.groupby("ProductCD", observed=True)
        .agg(
            transactions=("p_fraud", "size"),
            disputes=(LABEL, "sum"),
            approved_fraud=("action", lambda s: 0),  # filled below
            value_inr=("amount_inr", "sum"),
        )
        .reset_index()
    )
    approved = out[out["action"] == "APPROVE"]
    approved_fraud = approved[approved[LABEL] == 1].groupby("ProductCD", observed=True).size()
    seg["approved_fraud"] = seg["ProductCD"].map(approved_fraud).fillna(0).astype(int)
    seg["dispute_rate"] = seg["disputes"] / seg["transactions"]
    seg["residual_rate"] = seg["approved_fraud"] / seg["transactions"]
    seg = seg.sort_values("disputes", ascending=False)
    seg.to_csv(ARTIFACT_DIR / "segments.csv", index=False)
    print(f"Wrote {len(seg)} portfolio segments -> {ARTIFACT_DIR / 'segments.csv'}")

    summary = {
        "transactions": int(len(out)),
        "fold_days": int(out["day"].max() + 1),
        "fraud_rate": float(out[LABEL].mean()),
        "value_inr": float(out["amount_inr"].sum()),
        "actions": {k: int(v) for k, v in out["action"].value_counts().items()},
        "approved_fraud": int(((out["action"] == "APPROVE") & (out[LABEL] == 1)).sum()),
        "blocked_legit": int(((out["action"] == "BLOCK") & (out[LABEL] == 0)).sum()),
        "usd_inr": USD_INR,
    }
    (ARTIFACT_DIR / "decisions_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
