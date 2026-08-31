"""Turn held-out predictions into rupees, then into VAMP basis points.

    python -m ml.evaluate_money

Runs after `ml.train`. Three sections, in the order a reviewer should read them:

  1. What each strategy costs on the held-out fold, in rupees per 1,000
     transactions — the brief's "false-positive cost", stated as money.
  2. How much of that conclusion survives when the cost assumptions move, since
     every one of them is an estimate rather than a measurement.
  3. What it means for the acquirer's monitoring position, because `isFraud` in
     this dataset *is* a reported chargeback — so approved fraud maps directly
     onto the dispute count that VAMP measures.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict

import numpy as np

from ml.money import USD_INR, compare, sweep_assumption
from ml.policy import CostModel
from ml.vamp import PortfolioState, ThresholdTable, basis_points, project_defence

ARTIFACT_DIR = Path(__file__).resolve().parent.parent / "artifacts"

REQUIRED = ("test_p", "test_y", "test_amount", "calib_p", "calib_y", "calib_amount")


def load_arrays() -> Dict[str, np.ndarray]:
    missing = [n for n in REQUIRED if not (ARTIFACT_DIR / f"{n}.npy").exists()]
    if missing:
        raise SystemExit(
            f"Missing artifacts: {', '.join(missing)}\nRun `python -m ml.train` first."
        )
    return {n: np.load(ARTIFACT_DIR / f"{n}.npy") for n in REQUIRED}


def rule(title: str) -> None:
    print(f"\n{title}")
    print("=" * len(title))


def main() -> int:
    a = load_arrays()
    costs = CostModel()

    def run(c: CostModel):
        return compare(
            p_test=a["test_p"], y_test=a["test_y"], amounts_test_usd=a["test_amount"],
            p_calib=a["calib_p"], y_calib=a["calib_y"], amounts_calib_usd=a["calib_amount"],
            costs=c,
        )

    # ---- 1. money ----------------------------------------------------
    rule("1. REALISED COST ON THE HELD-OUT FOLD")
    print(f"  {len(a['test_y']):,} transactions, {a['test_y'].mean():.2%} fraudulent")
    print(f"  ticket amounts converted at {USD_INR:.0f} INR/USD\n")
    comparison = run(costs)
    print(comparison.table())

    # ---- 2. does it survive the assumptions? -------------------------
    rule("2. SENSITIVITY — where the advantage holds")
    print("  Every cost below is an estimate. If the policy only wins for one\n"
          "  particular setting, that is worth knowing and reporting.\n")

    sweeps = {
        "dispute_fee": [0.0, 400.0, 850.0, 2_000.0, 5_000.0],
        "false_decline_multiplier": [0.5, 1.0, 1.5, 2.5],
        "review_cost": [100.0, 450.0, 1_200.0],
        "step_up_abandon_rate": [0.01, 0.045, 0.10, 0.20],
    }
    for field, values in sweeps.items():
        print(f"  {field}")
        for row in sweep_assumption(field, values, costs, run):
            verdict = "policy wins" if row["saving_per_1k_inr"] > 0 else "NO ADVANTAGE"
            print(
                f"    {row[field]:>10,.3f}  ->  Rs {row['saving_per_1k_inr']:>10,.0f} / 1k "
                f"({row['saving_pct']:>6.1%})  {verdict}"
            )
        print()

    # ---- 3. the acquirer's position ----------------------------------
    rule("3. VAMP POSITION — what this is worth to the acquirer")
    thresholds = ThresholdTable()
    if not thresholds.verified:
        print("  [!] Thresholds are UNVERIFIED placeholders. Replace with Visa's")
        print("      published fact sheet before quoting any figure below.\n")

    n = len(a["test_y"])
    policy = next(r for r in comparison.results if r.name == "cost-optimal policy")
    baseline = comparison.best_baseline

    before = PortfolioState(settled_transactions=n, disputes=baseline.fraud_approved)
    after = PortfolioState(settled_transactions=n, disputes=policy.fraud_approved)
    prevented = baseline.fraud_approved - policy.fraud_approved

    print("  Every approved fraud in this dataset IS a reported chargeback, so")
    print("  approved-fraud count maps straight onto the VAMP dispute count.\n")
    print(f"  [!] This fold is {a['test_y'].mean():.2%} fraudulent. A real acquirer book runs")
    print("      one to two orders of magnitude below that — IEEE-CIS is enriched")
    print("      e-commerce traffic, not a representative payment stream. So the")
    print("      absolute bands below are inflated and the BAND LABELS are not a")
    print("      claim about any real portfolio. The honest, transferable figure is")
    print("      the RELATIVE dispute reduction, which is scale-free.\n")
    print(f"  {'':<26}{'disputes':>10}{'ratio':>12}{'band':>18}")
    for label, state in ((f"baseline ({baseline.name})", before), ("cost-optimal policy", after)):
        print(
            f"  {label:<26}{state.disputes:>10,}{basis_points(state.ratio):>10.0f}bps"
            f"{thresholds.band_for(state.ratio).value:>18}"
        )

    if prevented > 0:
        proj = project_defence(before, disputes_defended=prevented, thresholds=thresholds)
        reduction = prevented / before.disputes if before.disputes else 0.0
        print(f"\n  disputes prevented        {prevented:>10,}")
        print(f"  RELATIVE reduction        {reduction:>13.1%}   <- the transferable number")
        print(f"  basis points removed      {proj.bps_saved:>13.1f}   (inflated: see note above)")
        print(f"  monitoring fines avoided  Rs {proj.fines_avoided_inr:>12,.0f}   (illustrative only)")
    else:
        print("\n  Policy did not reduce approved fraud versus the baseline on this fold.")

    (ARTIFACT_DIR / "money_report.json").write_text(
        json.dumps(
            {
                "strategies": [r.__dict__ for r in comparison.results],
                "saving_per_1k_inr": comparison.saving_per_1k_inr,
                "saving_pct": comparison.saving_pct,
                "best_baseline": comparison.best_baseline.name,
                "vamp_thresholds_verified": thresholds.verified,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print("\nWritten to artifacts/money_report.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
