"""Score the policy in rupees, against baselines that are given a fair chance.

This is the file the submission is judged on. Everything upstream produces a
calibrated probability; this converts probabilities into the number the brief
actually asks for — what the false positives cost.

THE RULES THAT KEEP THE COMPARISON HONEST
-----------------------------------------
1. Baselines are tuned on the calibration fold, never on test. A fixed-threshold
   baseline tuned on the test set is an oracle, and beating an oracle you built
   for yourself proves nothing.
2. The realised cost of a decision uses the *actual* label, so a policy that
   blocks good customers pays for them in full.
3. Costs are assumptions. `sweep_assumption` re-runs the whole comparison across
   a range for any one of them, and the write-up reports where the advantage
   survives and where it does not.
4. IEEE-CIS ticket amounts are USD; the cost model is in INR. The conversion is
   explicit and stated rather than quietly ignored.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from typing import Callable, Dict, Iterable, List, Optional, Sequence

import numpy as np

from ml.policy import Action, CostModel, Outcome, decide, expected_cost

USD_INR = 88.0
"""IEEE-CIS amounts are in USD. Stated here so the unit change is visible rather
than buried in a magic number."""


@dataclass
class StrategyResult:
    name: str
    total_cost_inr: float
    cost_per_1k_inr: float
    approved: int
    stepped_up: int
    reviewed: int
    blocked: int
    fraud_approved: int
    """Fraudulent transactions let through — these become chargebacks."""
    legit_blocked: int
    """Good customers refused — the false-positive count that has a price."""
    review_load: float
    """Share of traffic sent to a human."""

    def summary_row(self) -> str:
        return (
            f"  {self.name:<34}{self.cost_per_1k_inr:>13,.0f}"
            f"{self.fraud_approved:>12,}{self.legit_blocked:>13,}{self.review_load:>10.2%}"
        )


def _linear_coeffs(costs: CostModel, action: Action, outcome: Outcome) -> tuple[float, float]:
    """Express cost(action, outcome, amount) as `intercept + slope * amount`.

    Every branch of `CostModel.cost` is affine in the ticket, so two evaluations
    recover it exactly. That turns the whole accounting into vector arithmetic —
    which matters because the sensitivity sweep re-runs this thousands of times
    over ~90k rows, and a per-row Python loop makes that unusably slow.
    """
    at_zero = costs.cost(action, outcome, 0.0)
    at_one = costs.cost(action, outcome, 1.0)
    return at_zero, at_one - at_zero


def realised_cost(
    actions: np.ndarray,
    y: np.ndarray,
    amounts_inr: np.ndarray,
    costs: CostModel,
) -> float:
    """Total rupee cost of a set of decisions, given what actually happened."""
    total = 0.0
    for action_name in np.unique(actions):
        action = Action(action_name)
        mask = actions == action_name
        for outcome, label in ((Outcome.FRAUD, 1), (Outcome.LEGIT, 0)):
            sel = mask & (y == label)
            if not sel.any():
                continue
            intercept, slope = _linear_coeffs(costs, action, outcome)
            amt = amounts_inr[sel]
            total += float(intercept * amt.size + slope * amt.sum())
    return total


def _tally(
    name: str,
    actions: np.ndarray,
    y: np.ndarray,
    amounts_inr: np.ndarray,
    costs: CostModel,
) -> StrategyResult:
    n = len(y)
    approved = actions == Action.APPROVE.value
    blocked = actions == Action.BLOCK.value
    reviewed = actions == Action.REVIEW.value
    stepped = actions == Action.STEP_UP.value

    total = realised_cost(actions, y, amounts_inr, costs)
    return StrategyResult(
        name=name,
        total_cost_inr=total,
        cost_per_1k_inr=total / n * 1000.0,
        approved=int(approved.sum()),
        stepped_up=int(stepped.sum()),
        reviewed=int(reviewed.sum()),
        blocked=int(blocked.sum()),
        fraud_approved=int((approved & (y == 1)).sum()),
        legit_blocked=int((blocked & (y == 0)).sum()),
        review_load=float(reviewed.mean()),
    )


# ---------------------------------------------------------------------------
# strategies
# ---------------------------------------------------------------------------
def always(action: Action, n: int) -> np.ndarray:
    return np.full(n, action.value, dtype=object)


def fixed_threshold(p: np.ndarray, threshold: float) -> np.ndarray:
    """Block above the threshold, approve below. The industry-standard baseline."""
    return np.where(p >= threshold, Action.BLOCK.value, Action.APPROVE.value).astype(object)


def cost_optimal(
    p: np.ndarray,
    amounts_inr: np.ndarray,
    costs: CostModel,
    allowed: Sequence[Action] = tuple(Action),
) -> np.ndarray:
    """Per-transaction argmin over expected cost.

    Vectorised form of `policy.decide`. Because each action's expected cost is
    affine in both p and the ticket, the whole table is four columns of vector
    arithmetic and the choice is one argmin. `test_money.py` checks this agrees
    with the scalar implementation.
    """
    order = list(allowed)
    table = np.empty((len(order), len(p)), dtype=float)
    for i, action in enumerate(order):
        f_int, f_slope = _linear_coeffs(costs, action, Outcome.FRAUD)
        l_int, l_slope = _linear_coeffs(costs, action, Outcome.LEGIT)
        fraud = f_int + f_slope * amounts_inr
        legit = l_int + l_slope * amounts_inr
        table[i] = p * fraud + (1.0 - p) * legit

    picks = np.argmin(table, axis=0)  # ties resolve to the earliest action, as decide() does
    return np.array([order[i].value for i in picks], dtype=object)


def tune_threshold_on_calibration(
    p_calib: np.ndarray,
    y_calib: np.ndarray,
    amounts_calib_inr: np.ndarray,
    costs: CostModel,
    grid: Optional[Iterable[float]] = None,
) -> float:
    """Best block-threshold for the baseline, chosen on the calibration fold.

    The baseline is given every advantage the policy has except the per-ticket
    reasoning: same model, same calibration, threshold optimised for the same
    objective. What it cannot do is vary its cut-off with the ticket, which is
    the whole point of the comparison.
    """
    grid = grid if grid is not None else np.unique(np.quantile(p_calib, np.linspace(0.90, 0.9999, 120)))
    best_t, best_cost = 1.0, float("inf")
    for t in grid:
        actions = fixed_threshold(p_calib, float(t))
        c = realised_cost(actions, y_calib, amounts_calib_inr, costs)
        if c < best_cost:
            best_t, best_cost = float(t), c
    return best_t


# ---------------------------------------------------------------------------
# comparison
# ---------------------------------------------------------------------------
@dataclass
class Comparison:
    results: List[StrategyResult]
    best: StrategyResult
    best_baseline: StrategyResult
    saving_per_1k_inr: float
    saving_pct: float

    def table(self) -> str:
        lines = [
            f"  {'strategy':<34}{'₹ / 1k txns':>13}{'fraud thru':>12}{'good blocked':>13}{'review':>10}",
            "  " + "-" * 82,
        ]
        lines += [r.summary_row() for r in self.results]
        lines.append("")
        lines.append(
            f"  Cost-optimal policy saves ₹{self.saving_per_1k_inr:,.0f} per 1,000 transactions "
            f"({self.saving_pct:.1%}) versus the best baseline ({self.best_baseline.name})."
        )
        return "\n".join(lines)


def compare(
    p_test: np.ndarray,
    y_test: np.ndarray,
    amounts_test_usd: np.ndarray,
    p_calib: np.ndarray,
    y_calib: np.ndarray,
    amounts_calib_usd: np.ndarray,
    costs: CostModel,
    usd_inr: float = USD_INR,
) -> Comparison:
    """Run every strategy on the held-out fold and rank them by realised cost."""
    amt_test = amounts_test_usd * usd_inr
    amt_calib = amounts_calib_usd * usd_inr
    n = len(y_test)

    threshold = tune_threshold_on_calibration(p_calib, y_calib, amt_calib, costs)

    strategies: Dict[str, np.ndarray] = {
        "approve everything": always(Action.APPROVE, n),
        "review everything": always(Action.REVIEW, n),
        f"fixed threshold (p>={threshold:.4f})": fixed_threshold(p_test, threshold),
        "cost-optimal policy": cost_optimal(p_test, amt_test, costs),
    }

    results = [_tally(name, acts, y_test, amt_test, costs) for name, acts in strategies.items()]
    results.sort(key=lambda r: r.cost_per_1k_inr)

    best = results[0]
    baselines = [r for r in results if r.name != "cost-optimal policy"]
    best_baseline = min(baselines, key=lambda r: r.cost_per_1k_inr)
    policy = next(r for r in results if r.name == "cost-optimal policy")

    saving = best_baseline.cost_per_1k_inr - policy.cost_per_1k_inr
    return Comparison(
        results=results,
        best=best,
        best_baseline=best_baseline,
        saving_per_1k_inr=saving,
        saving_pct=saving / best_baseline.cost_per_1k_inr if best_baseline.cost_per_1k_inr else 0.0,
    )


def sweep_assumption(
    field: str,
    values: Iterable[float],
    costs: CostModel,
    run: Callable[[CostModel], Comparison],
) -> List[Dict[str, float]]:
    """Re-run the whole comparison while varying one cost assumption.

    Reports the range over which the policy's advantage holds, so a reader can
    see the conclusion's dependence on inputs nobody has measured precisely.
    """
    rows = []
    for v in values:
        comparison = run(replace(costs, **{field: v}))
        rows.append({
            field: v,
            "saving_per_1k_inr": comparison.saving_per_1k_inr,
            "saving_pct": comparison.saving_pct,
            "best_baseline": comparison.best_baseline.name,
        })
    return rows
