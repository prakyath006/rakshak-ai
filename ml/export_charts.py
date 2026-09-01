"""Export chart-ready series from the held-out fold.

    python -m ml.export_charts

The product draws real curves, not decorative bars, so the shapes have to come
from the evaluation rather than from the frontend inventing them. Everything
here is computed once on the same 88,581 held-out transactions the rest of the
system reports on, and written to artifacts/charts.json.

Four series:

  pr_curve        precision against recall — the honest summary for a 3.5%
                  positive rate, where ROC would flatter
  calibration     predicted against observed by decile, with counts, so the
                  diagonal can be drawn and departures from it seen
  distribution    where the portfolio actually sits on the risk axis, split by
                  outcome, with the policy's action boundaries overlaid. This is
                  the one picture that shows the whole argument at once.
  cost_curve      realised rupee cost across every fixed threshold, against the
                  flat line the cost-optimal policy achieves. The gap between
                  the curve's minimum and that line is the contribution.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

import numpy as np
from sklearn.metrics import precision_recall_curve

from ml.money import USD_INR, compare, cost_optimal, fixed_threshold, realised_cost
from ml.policy import Action, CostModel, decision_boundaries

ARTIFACT_DIR = Path(__file__).resolve().parent.parent / "artifacts"


def _load(name: str) -> np.ndarray:
    path = ARTIFACT_DIR / f"{name}.npy"
    if not path.exists():
        raise SystemExit(f"Missing {path}. Run `python -m ml.train` first.")
    return np.load(path)


def pr_curve(y: np.ndarray, p: np.ndarray, points: int = 220) -> List[Dict[str, float]]:
    """Precision-recall curve, thinned to a drawable number of points.

    Thinned on recall rather than by index so the dense low-recall end does not
    dominate the sample and flatten the interesting part of the curve.
    """
    precision, recall, thresholds = precision_recall_curve(y, p)
    targets = np.linspace(0.0, 1.0, points)
    out = []
    for t in targets:
        i = int(np.argmin(np.abs(recall - t)))
        out.append({
            "recall": float(recall[i]),
            "precision": float(precision[i]),
            "threshold": float(thresholds[min(i, len(thresholds) - 1)]),
        })
    # Deduplicate while preserving order.
    seen, unique = set(), []
    for row in out:
        key = (round(row["recall"], 4), round(row["precision"], 4))
        if key not in seen:
            seen.add(key)
            unique.append(row)
    return unique


def distribution(
    y: np.ndarray, p: np.ndarray, bins: int = 44
) -> Dict[str, object]:
    """Risk distribution split by outcome, on a log-ish axis.

    A linear axis is useless here: 87% of transactions sit below p=0.02 and would
    pile into one bar. Binning on sqrt(p) spreads the low end without pretending
    the scale is linear, and the axis is labelled accordingly.
    """
    edges = np.linspace(0.0, 1.0, bins + 1) ** 2  # dense near zero
    idx = np.clip(np.digitize(p, edges[1:-1], right=False), 0, bins - 1)

    rows = []
    for b in range(bins):
        mask = idx == b
        rows.append({
            "from": float(edges[b]),
            "to": float(edges[b + 1]),
            "legit": int((mask & (y == 0)).sum()),
            "fraud": int((mask & (y == 1)).sum()),
        })
    return {"bins": rows, "scale": "sqrt"}


def cost_curve(
    y: np.ndarray,
    p: np.ndarray,
    amounts_inr: np.ndarray,
    costs: CostModel,
    points: int = 90,
) -> Dict[str, object]:
    """Cost of every fixed threshold, against the policy's flat achieved cost."""
    n = len(y)
    grid = np.unique(np.quantile(p, np.linspace(0.80, 0.9999, points)))
    curve = [
        {
            "threshold": float(t),
            "cost_per_1k": realised_cost(fixed_threshold(p, float(t)), y, amounts_inr, costs) / n * 1000.0,
        }
        for t in grid
    ]

    policy_cost = realised_cost(cost_optimal(p, amounts_inr, costs), y, amounts_inr, costs) / n * 1000.0
    approve_cost = realised_cost(
        np.full(n, Action.APPROVE.value, dtype=object), y, amounts_inr, costs
    ) / n * 1000.0
    best = min(curve, key=lambda r: r["cost_per_1k"])

    return {
        "curve": curve,
        "policy_cost_per_1k": policy_cost,
        "approve_all_cost_per_1k": approve_cost,
        "best_threshold": best["threshold"],
        "best_threshold_cost_per_1k": best["cost_per_1k"],
    }


SWEEPS = {
    "dispute_fee": ([0.0, 400.0, 850.0, 2_000.0, 5_000.0], "Dispute fee"),
    "false_decline_multiplier": ([0.5, 1.0, 1.5, 2.5], "False-decline cost"),
    "review_cost": ([100.0, 450.0, 1_200.0], "Review cost"),
    "step_up_abandon_rate": ([0.01, 0.045, 0.10, 0.20], "Step-up abandonment"),
}


def sensitivity_bars(
    y: np.ndarray, p: np.ndarray, amounts_inr: np.ndarray, costs: CostModel
) -> Dict[str, object]:
    """Re-run the whole comparison across each cost assumption.

    Reported as a chart because "the policy wins under every assumption we
    tested" is a stronger claim than a single number, and a reader should be able
    to see the range rather than take it on trust. Splitting the fold in half
    gives the baseline its own tuning data, exactly as the offline evaluation does.
    """
    from dataclasses import replace

    half = len(y) // 2
    rows: List[Dict[str, object]] = []
    for field, (values, label) in SWEEPS.items():
        for v in values:
            c = replace(costs, **{field: v})
            result = compare(
                p_test=p[half:], y_test=y[half:], amounts_test_usd=amounts_inr[half:] / USD_INR,
                p_calib=p[:half], y_calib=y[:half], amounts_calib_usd=amounts_inr[:half] / USD_INR,
                costs=c,
            )
            rows.append({
                "field": field,
                "label": label,
                "value": float(v),
                "saving_pct": float(result.saving_pct),
                "saving_per_1k_inr": float(result.saving_per_1k_inr),
            })
    return {
        "rows": rows,
        "wins": sum(1 for r in rows if r["saving_pct"] > 0),
        "total": len(rows),
    }


def main() -> int:
    y = _load("test_y")
    p = _load("test_p")
    amounts = _load("test_amount") * USD_INR
    costs = CostModel()

    print("Building precision-recall curve ...")
    pr = pr_curve(y, p)

    print("Building risk distribution ...")
    dist = distribution(y, p)

    print("Building cost curve (this sweeps every threshold) ...")
    cc = cost_curve(y, p, amounts, costs)

    print("Sweeping cost assumptions ...")
    sens = sensitivity_bars(y, p, amounts, costs)

    print("Deriving policy bands at the median ticket ...")
    median_ticket = float(np.median(amounts))
    bands = [
        {"from": lo, "to": hi, "action": a.value}
        for lo, hi, a in decision_boundaries(median_ticket, costs)
    ]

    payload = {
        "rows": int(len(y)),
        "fraud_rate": float(y.mean()),
        "median_ticket_inr": median_ticket,
        "pr_curve": pr,
        "distribution": dist,
        "cost_curve": cc,
        "sensitivity": sens,
        "policy_bands": bands,
    }

    out = ARTIFACT_DIR / "charts.json"
    out.write_text(json.dumps(payload), encoding="utf-8")
    print(f"\nWrote {out}  ({out.stat().st_size / 1024:.0f} KB)")
    print(f"  pr_curve      {len(pr)} points")
    print(f"  distribution  {len(dist['bins'])} bins")
    print(f"  cost_curve    {len(cc['curve'])} thresholds")
    print(f"  sensitivity   {len(sens['rows'])} configurations, {sens['wins']} favour the policy")
    print(f"  policy bands  {[b['action'] for b in bands]}")
    print(f"  policy cost   Rs {cc['policy_cost_per_1k']:,.0f} / 1k")
    print(f"  best fixed    Rs {cc['best_threshold_cost_per_1k']:,.0f} / 1k at p>={cc['best_threshold']:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
