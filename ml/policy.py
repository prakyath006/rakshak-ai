"""Cost-optimal action policy.

A risk model outputs a probability. A risk *system* has to output an action, and
every action has a price that depends on whether the transaction turns out to be
fraudulent. Those prices are not symmetric:

    blocking a good ₹40,000 order   costs the basket
    approving a bad ₹40,000 order   costs the goods, the dispute fee, and a
                                    contribution to the acquirer's VAMP ratio
    sending it to an analyst        costs a few hundred rupees of labour

A model tuned to maximise F1 treats those as interchangeable. They are not, so
this module picks the action with the lowest *expected rupee cost* instead of
thresholding a score.

    EC(action | p) = p · cost(action, fraud) + (1 − p) · cost(action, legitimate)
    chosen         = argmin over actions

Two things follow that make this more than a formula:

  1. Because expected cost is linear in p, the optimal action as a function of p
     is the lower envelope of a set of straight lines. The boundaries between
     actions are therefore *derived*, not tuned — see `decision_boundaries`.
  2. Every number in `CostModel` is an assumption. `sensitivity` exists so the
     assumptions get stress-tested and reported rather than quietly believed.

The probability handed to `decide` must be calibrated. An uncalibrated score
makes every expression here arithmetic on a number that is not a probability.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Dict, Iterable, List, Sequence, Tuple


class Action(str, Enum):
    """Actions available at authorisation time, cheapest intervention first."""

    APPROVE = "APPROVE"
    STEP_UP = "STEP_UP"      # 3-D Secure / OTP challenge
    REVIEW = "REVIEW"        # hold for a human analyst
    BLOCK = "BLOCK"


class Outcome(str, Enum):
    FRAUD = "FRAUD"          # would end in a chargeback
    LEGIT = "LEGIT"


@dataclass(frozen=True)
class CostModel:
    """Per-transaction economics, in rupees unless stated.

    Defaults are deliberately conservative placeholders for an Indian card-not-
    present merchant. They are *assumptions*, and the submission reports a
    sensitivity sweep over them rather than presenting them as measurements.
    """

    # --- loss when a fraudulent transaction is approved -------------------
    dispute_fee: float = 850.0
    """Flat fee charged back to the merchant per dispute, independent of ticket."""

    goods_recovery_rate: float = 0.0
    """Fraction of the ticket recovered when goods ship to a fraudster. Digital
    goods and most physical CNP fraud recover nothing."""

    vamp_marginal_cost: float = 0.0
    """Acquirer-side cost attributed to one additional dispute, from vamp.py.
    Zero when the portfolio sits comfortably below the monitoring thresholds;
    materially non-zero as it approaches them."""

    # --- loss when a legitimate transaction is refused --------------------
    false_decline_multiplier: float = 1.0
    """Cost of wrongly refusing a good customer, as a multiple of the ticket.
    1.0 counts only the lost basket and ignores churn, so it understates the
    true cost — deliberately, to avoid flattering the policy."""

    # --- step-up (3DS) ----------------------------------------------------
    step_up_bypass_rate: float = 0.12
    """Fraction of fraudsters who clear a challenge anyway."""

    step_up_abandon_rate: float = 0.045
    """Fraction of legitimate customers who abandon checkout at a challenge."""

    # --- manual review ----------------------------------------------------
    review_cost: float = 450.0
    """Fully-loaded analyst cost of one manual review."""

    review_accuracy: float = 0.92
    """Probability the analyst reaches the correct verdict."""

    def full_fraud_loss(self, amount: float) -> float:
        """Everything one approved fraudulent transaction costs."""
        goods = amount * (1.0 - self.goods_recovery_rate)
        return goods + self.dispute_fee + self.vamp_marginal_cost

    def false_decline_loss(self, amount: float) -> float:
        """Everything one wrongly-refused legitimate transaction costs."""
        return amount * self.false_decline_multiplier

    # ------------------------------------------------------------------
    def cost(self, action: Action, outcome: Outcome, amount: float) -> float:
        """Cost of taking `action` when the truth turns out to be `outcome`."""
        fraud_loss = self.full_fraud_loss(amount)
        decline_loss = self.false_decline_loss(amount)

        if action is Action.APPROVE:
            return fraud_loss if outcome is Outcome.FRAUD else 0.0

        if action is Action.BLOCK:
            return 0.0 if outcome is Outcome.FRAUD else decline_loss

        if action is Action.STEP_UP:
            if outcome is Outcome.FRAUD:
                # Only the fraudsters who defeat the challenge cost anything.
                return self.step_up_bypass_rate * fraud_loss
            # Some good customers give up at the challenge.
            return self.step_up_abandon_rate * decline_loss

        if action is Action.REVIEW:
            miss = 1.0 - self.review_accuracy
            if outcome is Outcome.FRAUD:
                return self.review_cost + miss * fraud_loss
            return self.review_cost + miss * decline_loss

        raise ValueError(f"Unhandled action: {action}")


@dataclass(frozen=True)
class Decision:
    action: Action
    expected_cost: float
    """Expected rupee cost of the chosen action."""
    costs: Dict[Action, float]
    """Expected cost of every action, so the choice can be explained."""
    regret_vs_approve: float
    """How much cheaper this is than approving. Negative means approving wins."""


def expected_cost(
    action: Action,
    p_fraud: float,
    amount: float,
    costs: CostModel,
) -> float:
    """EC(action | p) — linear in p, which is what makes the envelope exact."""
    return (
        p_fraud * costs.cost(action, Outcome.FRAUD, amount)
        + (1.0 - p_fraud) * costs.cost(action, Outcome.LEGIT, amount)
    )


def decide(
    p_fraud: float,
    amount: float,
    costs: CostModel,
    allowed: Sequence[Action] = tuple(Action),
) -> Decision:
    """Pick the cheapest defensible action for one transaction.

    `allowed` lets a merchant disable actions they cannot operate — a merchant
    with no analyst team removes REVIEW and the policy re-derives its boundaries
    around what is actually available.
    """
    if not 0.0 <= p_fraud <= 1.0:
        raise ValueError(f"p_fraud must be a probability, got {p_fraud}")
    if not allowed:
        raise ValueError("At least one action must be allowed")

    table = {a: expected_cost(a, p_fraud, amount, costs) for a in allowed}
    best = min(table, key=lambda a: (table[a], list(Action).index(a)))

    approve = table.get(Action.APPROVE, expected_cost(Action.APPROVE, p_fraud, amount, costs))
    return Decision(
        action=best,
        expected_cost=table[best],
        costs=table,
        regret_vs_approve=approve - table[best],
    )


def decision_boundaries(
    amount: float,
    costs: CostModel,
    allowed: Sequence[Action] = tuple(Action),
) -> List[Tuple[float, float, Action]]:
    """The exact probability bands over which each action is optimal.

    Expected cost is linear in p, so the optimal action is the lower envelope of
    |allowed| straight lines. Rather than sampling a grid, solve every pairwise
    crossing, then identify the winner on each resulting interval. Returns
    ``[(p_low, p_high, action), ...]`` covering [0, 1] with adjacent duplicate
    bands merged.

    This is the part worth showing a merchant: no threshold was hand-tuned, and
    each boundary answers "above this probability, this action is cheaper."
    """
    lines = {
        a: (
            costs.cost(a, Outcome.LEGIT, amount),  # intercept at p=0
            costs.cost(a, Outcome.FRAUD, amount) - costs.cost(a, Outcome.LEGIT, amount),  # slope
        )
        for a in allowed
    }

    cuts = {0.0, 1.0}
    actions = list(lines)
    for i, a1 in enumerate(actions):
        for a2 in actions[i + 1 :]:
            (b1, m1), (b2, m2) = lines[a1], lines[a2]
            if abs(m1 - m2) < 1e-12:
                continue  # parallel: no crossing
            p = (b2 - b1) / (m1 - m2)
            if 0.0 < p < 1.0:
                cuts.add(p)

    ordered = sorted(cuts)
    bands: List[Tuple[float, float, Action]] = []
    for low, high in zip(ordered, ordered[1:]):
        if high - low < 1e-12:
            continue
        winner = decide((low + high) / 2.0, amount, costs, allowed).action
        if bands and bands[-1][2] is winner:
            bands[-1] = (bands[-1][0], high, winner)
        else:
            bands.append((low, high, winner))
    return bands


def sensitivity(
    amount: float,
    costs: CostModel,
    field: str,
    values: Iterable[float],
    allowed: Sequence[Action] = tuple(Action),
) -> List[Tuple[float, List[Tuple[float, float, Action]]]]:
    """Re-derive the boundaries while sweeping one cost assumption.

    Every number in `CostModel` is an estimate. This is how the submission shows
    where its conclusions hold and where they fall apart, instead of presenting a
    single figure resting on unexamined inputs.
    """
    if not hasattr(costs, field):
        raise AttributeError(f"CostModel has no field {field!r}")
    return [
        (v, decision_boundaries(amount, replace(costs, **{field: v}), allowed))
        for v in values
    ]
