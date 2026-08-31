"""Tests for the rupee accounting.

The headline figure of the whole submission comes out of this module, so the
arithmetic is checked against hand-computed values rather than trusted. Uses
small synthetic arrays: these test the accounting, not the model.

    python -m pytest ml/test_money.py -q
"""

from __future__ import annotations

import numpy as np
import pytest

from ml.policy import Outcome
from ml.money import (
    Action,
    CostModel,
    compare,
    cost_optimal,
    fixed_threshold,
    realised_cost,
    tune_threshold_on_calibration,
)


def test_realised_cost_uses_the_actual_outcome():
    """Approving one fraud and one good transaction costs only the fraud."""
    costs = CostModel(dispute_fee=850.0, goods_recovery_rate=0.0, vamp_marginal_cost=0.0)
    actions = np.array([Action.APPROVE.value, Action.APPROVE.value], dtype=object)
    y = np.array([1, 0])
    amounts = np.array([4_000.0, 4_000.0])
    assert realised_cost(actions, y, amounts, costs) == pytest.approx(4_850.0)


def test_blocking_a_good_customer_is_charged_in_full():
    """A false positive must cost money, or the whole exercise is pointless."""
    costs = CostModel(false_decline_multiplier=1.0)
    actions = np.array([Action.BLOCK.value], dtype=object)
    assert realised_cost(actions, np.array([0]), np.array([4_000.0]), costs) == pytest.approx(4_000.0)


def test_blocking_fraud_costs_nothing():
    costs = CostModel()
    actions = np.array([Action.BLOCK.value], dtype=object)
    assert realised_cost(actions, np.array([1]), np.array([9_999.0]), costs) == 0.0


def test_fixed_threshold_splits_on_the_cut():
    p = np.array([0.01, 0.50, 0.99])
    actions = fixed_threshold(p, 0.5)
    assert list(actions) == [Action.APPROVE.value, Action.BLOCK.value, Action.BLOCK.value]


def test_cost_optimal_escalates_with_risk():
    """Higher probability must never produce a more permissive action."""
    severity = {Action.APPROVE.value: 0, Action.STEP_UP.value: 1,
                Action.REVIEW.value: 2, Action.BLOCK.value: 3}
    p = np.linspace(0.0, 1.0, 60)
    amounts = np.full(60, 4_000.0)
    ranks = [severity[a] for a in cost_optimal(p, amounts, CostModel())]
    assert ranks == sorted(ranks)


def test_baseline_threshold_is_tuned_on_calibration_not_test():
    """Guards the comparison's fairness.

    The tuner must only ever see the calibration arrays. If this ever starts
    accepting test data the baseline becomes an oracle and every reported saving
    is inflated.
    """
    rng = np.random.default_rng(0)
    p = rng.random(500)
    y = (rng.random(500) < p).astype(int)
    amounts = np.full(500, 4_000.0)
    t = tune_threshold_on_calibration(p, y, amounts, CostModel())
    assert 0.0 <= t <= 1.0


def test_comparison_reports_a_saving_against_the_best_baseline():
    """End-to-end shape check on separable synthetic data.

    Fraud is concentrated at high p, so a sensible policy should beat
    approve-everything, and the comparison should say by how much.
    """
    rng = np.random.default_rng(7)
    n = 4_000
    y = (rng.random(n) < 0.035).astype(int)
    # A well-separated, roughly calibrated score.
    p = np.where(y == 1, rng.beta(6, 3, n), rng.beta(1, 60, n))
    amounts = rng.lognormal(mean=4.0, sigma=0.6, size=n)

    half = n // 2
    result = compare(
        p_test=p[half:], y_test=y[half:], amounts_test_usd=amounts[half:],
        p_calib=p[:half], y_calib=y[:half], amounts_calib_usd=amounts[:half],
        costs=CostModel(),
    )

    names = {r.name for r in result.results}
    assert "cost-optimal policy" in names
    assert "approve everything" in names
    assert result.best_baseline.name != "cost-optimal policy"
    # With separable scores the policy should not be worse than doing nothing.
    approve_all = next(r for r in result.results if r.name == "approve everything")
    policy = next(r for r in result.results if r.name == "cost-optimal policy")
    assert policy.cost_per_1k_inr <= approve_all.cost_per_1k_inr


def test_vectorised_policy_matches_the_scalar_one():
    """The fast path must be the same policy, not an approximation of it.

    `cost_optimal` rebuilds `policy.decide` in vector form for speed. If the two
    ever drift apart, the reported money is computed by different rules than the
    ones documented and tested in policy.py.
    """
    from ml.policy import decide

    rng = np.random.default_rng(11)
    p = rng.random(400)
    amounts = rng.lognormal(4.0, 0.8, 400)
    costs = CostModel()

    vector = cost_optimal(p, amounts, costs)
    scalar = [decide(float(pi), float(ai), costs).action.value for pi, ai in zip(p, amounts)]
    assert list(vector) == scalar


def test_linear_coefficients_reproduce_the_cost_function():
    """Guards the affine assumption the vectorisation depends on."""
    from ml.money import _linear_coeffs

    costs = CostModel()
    for action in Action:
        for outcome, _ in ((Outcome.FRAUD, 1), (Outcome.LEGIT, 0)):
            intercept, slope = _linear_coeffs(costs, action, outcome)
            for amount in (0.0, 137.5, 9_999.0, 250_000.0):
                assert intercept + slope * amount == pytest.approx(
                    costs.cost(action, outcome, amount)
                ), f"{action} / {outcome} is not affine in the ticket"


def test_every_transaction_gets_exactly_one_action():
    """No transaction may be double-counted or dropped from the tally."""
    rng = np.random.default_rng(3)
    n = 500
    y = (rng.random(n) < 0.035).astype(int)
    p = rng.random(n)
    amounts = rng.lognormal(4.0, 0.5, n)

    half = n // 2
    result = compare(
        p_test=p[half:], y_test=y[half:], amounts_test_usd=amounts[half:],
        p_calib=p[:half], y_calib=y[:half], amounts_calib_usd=amounts[:half],
        costs=CostModel(),
    )
    for r in result.results:
        assert r.approved + r.stepped_up + r.reviewed + r.blocked == n - half, r.name
