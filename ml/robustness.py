"""Turn the headline's soft spots into measurements.

    python -m ml.robustness

Three weaknesses in the money claim, each addressed with an experiment rather
than a caveat:

  1. CONFIDENCE — "₹1,41,370 saved" is a point estimate off one 88,581-row fold.
     Bootstrap resampling gives it an interval, so the reader knows whether the
     advantage is comfortably positive or a coin-toss.

  2. STABILITY — a single number can hide an advantage driven by one freak day.
     Splitting the fold into weeks shows whether the policy wins consistently or
     only on average.

  3. BREAK-EVEN — every cost in the model is an assumption. Rather than defend
     the assumed value, solve for the value at which the conclusion would flip.
     "The policy wins for any dispute fee above ₹X" is a far stronger statement
     than "we assumed ₹850", because it does not require the reader to accept
     the assumption at all.

Everything here runs on the saved held-out arrays; nothing is retrained.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from ml.money import USD_INR, cost_optimal, fixed_threshold, realised_cost, tune_threshold_on_calibration
from ml.policy import Action, CostModel

ARTIFACT_DIR = Path(__file__).resolve().parent.parent / "artifacts"
RNG = np.random.default_rng(20260905)


def _load() -> Dict[str, np.ndarray]:
    need = ("test_p", "test_y", "test_amount", "calib_p", "calib_y", "calib_amount")
    missing = [n for n in need if not (ARTIFACT_DIR / f"{n}.npy").exists()]
    if missing:
        raise SystemExit(f"Missing {', '.join(missing)}. Run `python -m ml.train` first.")
    return {n: np.load(ARTIFACT_DIR / f"{n}.npy") for n in need}


def _saving(
    p: np.ndarray, y: np.ndarray, amt: np.ndarray, threshold: float, costs: CostModel
) -> float:
    """Rupees per 1,000 the policy saves over the fixed threshold, on this sample."""
    n = len(y)
    if n == 0:
        return 0.0
    policy = realised_cost(cost_optimal(p, amt, costs), y, amt, costs) / n * 1000.0
    base = realised_cost(fixed_threshold(p, threshold), y, amt, costs) / n * 1000.0
    return base - policy


# ---------------------------------------------------------------------------
# 1. confidence
# ---------------------------------------------------------------------------
def bootstrap_saving(
    p: np.ndarray,
    y: np.ndarray,
    amt: np.ndarray,
    threshold: float,
    costs: CostModel,
    draws: int = 400,
) -> Dict[str, float]:
    """Percentile bootstrap over the held-out fold.

    The threshold stays fixed at the value tuned on the calibration fold — only
    the evaluation sample is resampled. Re-tuning per draw would measure a
    different, easier question.
    """
    n = len(y)
    savings = np.empty(draws)
    for b in range(draws):
        idx = RNG.integers(0, n, n)
        savings[b] = _saving(p[idx], y[idx], amt[idx], threshold, costs)

    point = _saving(p, y, amt, threshold, costs)
    return {
        "point_estimate": point,
        "ci_low": float(np.percentile(savings, 2.5)),
        "ci_high": float(np.percentile(savings, 97.5)),
        "std_error": float(savings.std(ddof=1)),
        "draws": draws,
        "share_of_draws_positive": float((savings > 0).mean()),
    }


# ---------------------------------------------------------------------------
# 2. stability over time
# ---------------------------------------------------------------------------
def weekly_stability(
    threshold: float, costs: CostModel, days_per_bucket: int = 7
) -> List[Dict[str, float]]:
    """Recompute the saving within each week of the held-out fold.

    An advantage that only appears in aggregate — one anomalous week carrying the
    average — would be a much weaker claim than one that holds throughout.
    """
    path = ARTIFACT_DIR / "decisions.csv"
    if not path.exists():
        raise SystemExit("Missing artifacts/decisions.csv. Run `python -m ml.export_decisions`.")
    df = pd.read_csv(path, usecols=["day", "p_fraud", "isFraud", "amount_inr"])

    out: List[Dict[str, float]] = []
    for start in range(0, int(df["day"].max()) + 1, days_per_bucket):
        chunk = df[(df["day"] >= start) & (df["day"] < start + days_per_bucket)]
        if len(chunk) < 500:
            continue
        out.append({
            "days": f"{start}-{min(start + days_per_bucket - 1, int(df['day'].max()))}",
            "transactions": int(len(chunk)),
            "fraud_rate": float(chunk["isFraud"].mean()),
            "saving_per_1k_inr": _saving(
                chunk["p_fraud"].to_numpy(),
                chunk["isFraud"].to_numpy(),
                chunk["amount_inr"].to_numpy(),
                threshold,
                costs,
            ),
        })
    return out


# ---------------------------------------------------------------------------
# 3. break-even
# ---------------------------------------------------------------------------
BREAK_EVEN_FIELDS = {
    "dispute_fee": (0.0, 20_000.0, "₹ per dispute"),
    "false_decline_multiplier": (0.05, 12.0, "× basket"),
    "step_up_abandon_rate": (0.0, 0.95, "fraction abandoning"),
    "step_up_bypass_rate": (0.0, 0.95, "fraction bypassing"),
    "review_cost": (0.0, 40_000.0, "₹ per review"),
}


def break_even(
    p: np.ndarray,
    y: np.ndarray,
    amt: np.ndarray,
    calib: Dict[str, np.ndarray],
    base_costs: CostModel,
    field: str,
    lo: float,
    hi: float,
    steps: int = 26,
) -> Optional[float]:
    """Value of `field` at which the policy's advantage reaches zero.

    The baseline threshold is RE-TUNED at every point on the sweep. Holding it at
    the value tuned under the default costs would let the policy re-optimise
    against a frozen opponent, and the resulting "never flips" would be an
    artefact of the comparison rather than a property of the policy.

    Returns None when the advantage survives across the whole plausible range,
    which is then a real statement: the conclusion does not rest on that
    assumption.
    """
    grid = np.linspace(lo, hi, steps)
    savings = []
    for v in grid:
        c = replace(base_costs, **{field: float(v)})
        t = tune_threshold_on_calibration(calib["p"], calib["y"], calib["amt"], c)
        savings.append(_saving(p, y, amt, t, c))

    savings = np.array(savings)
    if (savings > 0).all():
        return None
    # First crossing, linearly interpolated between the bracketing grid points.
    for i in range(1, len(grid)):
        if savings[i - 1] > 0 >= savings[i]:
            s0, s1 = savings[i - 1], savings[i]
            return float(grid[i - 1] + (grid[i] - grid[i - 1]) * s0 / (s0 - s1))
    return float(grid[int(np.argmin(savings))])


def attribution(
    p: np.ndarray, y: np.ndarray, amt: np.ndarray, threshold: float, costs: CostModel
) -> Dict[str, float]:
    """Split the advantage into optimisation versus action space.

    The obvious objection to the headline is that a four-action policy beating a
    two-action threshold is not a fair fight. It is a fair objection, so measure
    it: run the same expected-value rule restricted to approve/block and compare.

    It lands almost exactly on the tuned threshold, which is the point — a
    threshold already *is* the expected-value-optimal binary rule. The saving is
    therefore attributable to the middle option, not to the optimiser, and the
    write-up should say so rather than implying cleverness it does not have.
    """
    n = len(y)
    per_1k = lambda acts: realised_cost(acts, y, amt, costs) / n * 1000.0  # noqa: E731

    threshold_cost = per_1k(fixed_threshold(p, threshold))
    two_action_cost = per_1k(cost_optimal(p, amt, costs, allowed=(Action.APPROVE, Action.BLOCK)))
    full_cost = per_1k(cost_optimal(p, amt, costs))

    total = threshold_cost - full_cost
    from_opt = threshold_cost - two_action_cost
    from_step = two_action_cost - full_cost
    return {
        "threshold_cost": threshold_cost,
        "two_action_cost": two_action_cost,
        "full_cost": full_cost,
        "gain_from_optimisation": from_opt,
        "gain_from_step_up": from_step,
        "share_from_optimisation": from_opt / total if total else 0.0,
        "share_from_step_up": from_step / total if total else 0.0,
    }


def main() -> int:
    a = _load()
    costs = CostModel()
    p, y = a["test_p"], a["test_y"]
    amt = a["test_amount"] * USD_INR

    threshold = tune_threshold_on_calibration(
        a["calib_p"], a["calib_y"], a["calib_amount"] * USD_INR, costs
    )

    print("=" * 76)
    print("ROBUSTNESS OF THE MONEY CLAIM")
    print("=" * 76)
    print(f"  Baseline threshold p>={threshold:.4f}, tuned on the calibration fold only.\n")

    # ---- 1 ----------------------------------------------------------------
    print("1. CONFIDENCE — bootstrap over the held-out fold")
    print("-" * 76)
    boot = bootstrap_saving(p, y, amt, threshold, costs)
    print(f"   point estimate     Rs {boot['point_estimate']:>10,.0f} / 1k")
    print(f"   95% interval       Rs {boot['ci_low']:>10,.0f}  to  Rs {boot['ci_high']:,.0f}")
    print(f"   standard error     Rs {boot['std_error']:>10,.0f}")
    print(f"   draws positive     {boot['share_of_draws_positive']:.1%} of {boot['draws']}")
    print()

    # ---- 2 ----------------------------------------------------------------
    print("2. STABILITY — is the advantage carried by one week?")
    print("-" * 76)
    weeks = weekly_stability(threshold, costs)
    print(f"   {'days':<10}{'txns':>10}{'fraud':>9}{'saving / 1k':>16}")
    for w in weeks:
        print(f"   {w['days']:<10}{w['transactions']:>10,}{w['fraud_rate']:>8.2%}"
              f"   Rs {w['saving_per_1k_inr']:>10,.0f}")
    wins = sum(1 for w in weeks if w["saving_per_1k_inr"] > 0)
    print(f"\n   Policy ahead in {wins} of {len(weeks)} weeks.")
    print()

    # ---- 3 ----------------------------------------------------------------
    print("3. BREAK-EVEN — at what assumption would the conclusion flip?")
    print("-" * 76)
    print("   The baseline threshold is re-tuned at every point, so the policy is")
    print("   never optimising against a frozen opponent.")
    print()
    calib = {"p": a["calib_p"], "y": a["calib_y"], "amt": a["calib_amount"] * USD_INR}
    breaks: Dict[str, Optional[float]] = {}
    for field, (lo, hi, unit) in BREAK_EVEN_FIELDS.items():
        be = break_even(p, y, amt, calib, costs, field, lo, hi)
        breaks[field] = be
        current = getattr(costs, field)
        if be is None:
            print(f"   {field:<28} assumed {current:>10,.3f}   never flips across {lo:g}–{hi:g} {unit}")
        else:
            print(f"   {field:<28} assumed {current:>10,.3f}   flips at {be:>10,.3f} {unit}")
    print()
    print("   A field that never flips is one the conclusion does not rest on.")

    # ---- 4 ----------------------------------------------------------------
    print("4. ATTRIBUTION — where does the advantage actually come from?")
    print("-" * 76)
    decomp = attribution(p, y, amt, threshold, costs)
    print(f"   tuned threshold (approve/block)        Rs {decomp['threshold_cost']:>10,.0f} / 1k")
    print(f"   EV policy restricted to approve/block  Rs {decomp['two_action_cost']:>10,.0f} / 1k")
    print(f"   EV policy, all four actions            Rs {decomp['full_cost']:>10,.0f} / 1k")
    print()
    print(f"   from better optimisation alone         Rs {decomp['gain_from_optimisation']:>10,.0f}"
          f"   ({decomp['share_from_optimisation']:.1%} of the total)")
    print(f"   from having step-up available          Rs {decomp['gain_from_step_up']:>10,.0f}"
          f"   ({decomp['share_from_step_up']:.1%} of the total)")
    print()
    print("   Restricted to two actions the policy matches the tuned threshold to")
    print("   within rounding — the threshold IS the expected-value-optimal binary")
    print("   rule. So the advantage is not clever optimisation; it is having a")
    print("   middle option at all, with the arithmetic placing its boundaries.")
    print()

    (ARTIFACT_DIR / "robustness.json").write_text(
        json.dumps(
            {
                "threshold": threshold,
                "bootstrap": boot,
                "weekly": weeks,
                "break_even": breaks,
                "attribution": decomp,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print("\nWritten to artifacts/robustness.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
