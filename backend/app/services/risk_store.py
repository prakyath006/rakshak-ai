"""Serves the scored held-out fold to the API.

Everything the product displays comes from here, and everything here came out of
`ml/`: 88,581 real transactions from the final 31 days of IEEE-CIS, each with the
calibrated probability the model assigned and the action the cost policy chose.

The application never re-scores at request time. Loading a frozen export keeps
the UI honest — a figure on screen can always be traced to a specific held-out
prediction — and keeps request latency in milliseconds.

If the artifacts are absent the API still starts and reports `available: false`,
so the dispute-agent half of the product works without a trained model present.
"""

from __future__ import annotations

import json
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[3]
ARTIFACT_DIR = REPO_ROOT / "artifacts"

# ml/ lives at the repository root, beside backend/.
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


class RiskStore:
    """Lazy, read-only view over the model artifacts."""

    def __init__(self, artifact_dir: Path = ARTIFACT_DIR):
        self.dir = artifact_dir
        self._decisions = None
        self._segments = None

    # ------------------------------------------------------------------
    @property
    def available(self) -> bool:
        return (self.dir / "decisions.csv").exists() and (self.dir / "report.json").exists()

    def _load_json(self, name: str) -> Optional[Dict[str, Any]]:
        path = self.dir / name
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    @property
    def decisions(self):
        if self._decisions is None:
            import pandas as pd

            self._decisions = pd.read_csv(self.dir / "decisions.csv")
        return self._decisions

    @property
    def segments(self):
        if self._segments is None:
            import pandas as pd

            self._segments = pd.read_csv(self.dir / "segments.csv")
        return self._segments

    # ------------------------------------------------------------------
    def status(self) -> Dict[str, Any]:
        """What the model layer is, in the terms the UI needs to state it."""
        if not self.available:
            return {
                "available": False,
                "reason": (
                    "No model artifacts. Run `python -m ml.train` then "
                    "`python -m ml.export_decisions` to populate them."
                ),
            }
        report = self._load_json("report.json") or {}
        summary = self._load_json("decisions_summary.json") or {}
        return {
            "available": True,
            "dataset": "IEEE-CIS (Vesta) — label is a reported chargeback on the card",
            "rows_train": report.get("rows_train"),
            "rows_calib": report.get("rows_calib"),
            "rows_test": report.get("rows_test"),
            "split": "chronological by TransactionDT; folds checked for overlap",
            "fold_days": summary.get("fold_days"),
            "fraud_rate_test": report.get("fraud_rate_test"),
            "pr_auc": report.get("pr_auc"),
            "roc_auc": report.get("roc_auc"),
            "usd_inr": summary.get("usd_inr"),
        }

    def evaluation(self) -> Dict[str, Any]:
        """Model metrics — precision and recall lead, as the brief words it."""
        report = self._load_json("report.json")
        if report is None:
            return {"available": False}
        return {
            "available": True,
            "rows_test": report["rows_test"],
            "fraud_rate_test": report["fraud_rate_test"],
            "pr_auc": report["pr_auc"],
            "roc_auc": report["roc_auc"],
            "pr_auc_baseline": report["fraud_rate_test"],
            "lift": report["pr_auc"] / report["fraud_rate_test"] if report["fraud_rate_test"] else None,
            "brier_raw": report["brier_raw"],
            "brier_calibrated": report["brier_calibrated"],
            "operating_points": report["operating_points"],
            "calibration_bins": report["calibration_bins"],
            "top_features": report["top_features"][:15],
            "train_seconds": report.get("train_seconds"),
        }

    def charts(self) -> Dict[str, Any]:
        """Drawable series: PR curve, risk distribution, cost curve, policy bands.

        Computed offline by ml/export_charts.py on the same held-out fold, so the
        shapes the product draws are the evaluation's, not the frontend's.
        """
        payload = self._load_json("charts.json")
        if payload is None:
            return {"available": False}
        return {"available": True, **payload}

    def money(self) -> Dict[str, Any]:
        report = self._load_json("money_report.json")
        if report is None:
            return {"available": False}
        return {"available": True, **report}

    # ------------------------------------------------------------------
    def summary(self) -> Dict[str, Any]:
        if not self.available:
            return {"available": False}
        summary = self._load_json("decisions_summary.json") or {}
        money = self._load_json("money_report.json") or {}
        return {
            "available": True,
            **summary,
            "saving_per_1k_inr": money.get("saving_per_1k_inr"),
            "saving_pct": money.get("saving_pct"),
            "best_baseline": money.get("best_baseline"),
        }

    def queue(
        self,
        limit: int = 50,
        offset: int = 0,
        action: Optional[str] = None,
        segment: Optional[str] = None,
        min_probability: float = 0.0,
    ) -> Dict[str, Any]:
        """Transactions ordered by expected rupee loss — not by probability.

        A 90%-likely ₹200 fraud matters less than a 20%-likely ₹80,000 one. The
        queue is ranked the way the money says it should be.
        """
        df = self.decisions
        if action:
            df = df[df["action"] == action.upper()]
        if segment:
            df = df[df["ProductCD"] == segment]
        if min_probability > 0:
            df = df[df["p_fraud"] >= min_probability]

        total = len(df)
        page = df.iloc[offset : offset + limit]
        return {
            "total": total,
            "offset": offset,
            "limit": limit,
            "items": [_row_to_item(r) for _, r in page.iterrows()],
        }

    def segment_view(self) -> Dict[str, Any]:
        """Portfolio segments ranked by contribution to the book's dispute count."""
        if not self.available:
            return {"available": False, "segments": []}

        seg = self.segments
        total_txns = int(seg["transactions"].sum())
        total_disputes = int(seg["disputes"].sum())

        rows: List[Dict[str, Any]] = []
        for _, r in seg.iterrows():
            rows.append({
                "segment": str(r["ProductCD"]),
                "transactions": int(r["transactions"]),
                "disputes": int(r["disputes"]),
                "approved_fraud": int(r["approved_fraud"]),
                "own_rate_bps": float(r["dispute_rate"] * 10_000),
                "residual_rate_bps": float(r["residual_rate"] * 10_000),
                # The acquirer-side number: basis points this segment adds to the
                # whole book, which is what decides where effort belongs.
                "portfolio_bps_contributed": float(r["disputes"] / total_txns * 10_000),
                "value_inr": float(r["value_inr"]),
            })
        rows.sort(key=lambda x: x["portfolio_bps_contributed"], reverse=True)

        return {
            "available": True,
            "total_transactions": total_txns,
            "total_disputes": total_disputes,
            "portfolio_bps": total_disputes / total_txns * 10_000 if total_txns else 0.0,
            "segments": rows,
        }

    # ------------------------------------------------------------------
    def simulate_policy(self, overrides: Dict[str, float], amount_inr: float) -> Dict[str, Any]:
        """Re-derive the action boundaries under caller-supplied cost assumptions.

        This is what makes the cost model inspectable rather than a black box: a
        reviewer moves an assumption and watches the boundaries move, on the same
        arithmetic the offline evaluation uses.
        """
        from dataclasses import replace

        from ml.policy import CostModel, decision_boundaries

        base = CostModel()
        allowed = {f.name for f in base.__dataclass_fields__.values()}
        clean = {k: float(v) for k, v in overrides.items() if k in allowed}
        costs = replace(base, **clean)

        bands = decision_boundaries(amount_inr, costs)
        return {
            "amount_inr": amount_inr,
            "costs": {k: getattr(costs, k) for k in allowed},
            "applied_overrides": clean,
            "bands": [
                {"from": low, "to": high, "action": action.value}
                for low, high, action in bands
            ],
        }

    def defaults(self) -> Dict[str, float]:
        from ml.policy import CostModel

        base = CostModel()
        return {f.name: getattr(base, f.name) for f in base.__dataclass_fields__.values()}


def _row_to_item(r) -> Dict[str, Any]:
    def clean(value):
        # NaN is not valid JSON; the UI shows an em dash for a missing attribute.
        return None if value != value else value

    return {
        "transaction_id": int(r["TransactionID"]),
        "day": int(r["day"]),
        "amount_inr": float(r["amount_inr"]),
        "p_fraud": float(r["p_fraud"]),
        "expected_loss_inr": float(r["expected_loss_inr"]),
        "action": str(r["action"]),
        "is_fraud": int(r["isFraud"]),
        "segment": clean(str(r["ProductCD"]) if r["ProductCD"] == r["ProductCD"] else None),
        "card_network": clean(r.get("card4")),
        "card_type": clean(r.get("card6")),
        "email_domain": clean(r.get("P_emaildomain")),
        "device": clean(r.get("DeviceType")),
    }


@lru_cache
def get_risk_store() -> RiskStore:
    return RiskStore()
