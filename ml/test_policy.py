"""Tests for the cost policy and the VAMP portfolio layer.

These assert *properties* rather than frozen numbers wherever possible — the cost
assumptions are meant to be swept, so a test that pins them would have to be
rewritten every time someone questions an input. What must hold regardless of the
inputs is the shape: cheap actions win at low risk, expensive ones at high risk,
boundaries are monotone, and the acquirer's exposure rises near a threshold.

    python -m pytest ml/test_policy.py -q
"""

from __future__ import annotations

import pytest

from ml.policy import (
    Action,
    CostModel,
    Outcome,
    decide,
    decision_boundaries,
    expected_cost,
    sensitivity,
)
from ml.vamp import (
    Band,
    MerchantState,
    PortfolioState,
    ThresholdTable,
    headroom,
    marginal_dispute_cost_inr,
    project_defence,
    rank_merchants_by_portfolio_impact,
)

AMOUNT = 4_000.0


# ---------------------------------------------------------------------------
# cost model
# ---------------------------------------------------------------------------
def test_approving_a_good_transaction_is_free():
    costs = CostModel()
    assert costs.cost(Action.APPROVE, Outcome.LEGIT, AMOUNT) == 0.0


def test_approving_fraud_costs_goods_plus_fee():
    costs = CostModel(dispute_fee=850.0, goods_recovery_rate=0.0)
    assert costs.cost(Action.APPROVE, Outcome.FRAUD, AMOUNT) == pytest.approx(4_850.0)


def test_vamp_pressure_raises_the_cost_of_approving_fraud():
    """The acquirer-side externality has to actually reach the decision."""
    calm = CostModel(vamp_marginal_cost=0.0)
    near_threshold = CostModel(vamp_marginal_cost=700.0)
    assert (
        near_threshold.cost(Action.APPROVE, Outcome.FRAUD, AMOUNT)
        > calm.cost(Action.APPROVE, Outcome.FRAUD, AMOUNT)
    )


def test_blocking_fraud_is_free_and_blocking_good_costs_the_basket():
    costs = CostModel(false_decline_multiplier=1.0)
    assert costs.cost(Action.BLOCK, Outcome.FRAUD, AMOUNT) == 0.0
    assert costs.cost(Action.BLOCK, Outcome.LEGIT, AMOUNT) == pytest.approx(AMOUNT)


# ---------------------------------------------------------------------------
# the policy
# ---------------------------------------------------------------------------
def test_approve_when_risk_is_negligible():
    assert decide(0.0001, AMOUNT, CostModel()).action is Action.APPROVE


def test_block_when_risk_is_overwhelming():
    assert decide(0.99, AMOUNT, CostModel()).action is Action.BLOCK


def test_expected_cost_is_linear_in_probability():
    """Linearity is what makes the boundary solve exact rather than sampled."""
    costs = CostModel()
    lo = expected_cost(Action.APPROVE, 0.2, AMOUNT, costs)
    mid = expected_cost(Action.APPROVE, 0.4, AMOUNT, costs)
    hi = expected_cost(Action.APPROVE, 0.6, AMOUNT, costs)
    assert mid - lo == pytest.approx(hi - mid)


def test_decision_is_explainable():
    """Every action's cost is returned so a merchant can be told why."""
    d = decide(0.5, AMOUNT, CostModel())
    assert set(d.costs) == set(Action)
    assert d.expected_cost == pytest.approx(min(d.costs.values()))


def test_probability_must_be_valid():
    with pytest.raises(ValueError):
        decide(1.4, AMOUNT, CostModel())


# ---------------------------------------------------------------------------
# boundaries
# ---------------------------------------------------------------------------
def test_boundaries_tile_the_unit_interval():
    bands = decision_boundaries(AMOUNT, CostModel())
    assert bands[0][0] == pytest.approx(0.0)
    assert bands[-1][1] == pytest.approx(1.0)
    for (_, high), (low, _) in zip(
        [(b[0], b[1]) for b in bands], [(b[0], b[1]) for b in bands[1:]]
    ):
        assert high == pytest.approx(low)


def test_boundaries_run_from_permissive_to_restrictive():
    """Risk tolerance must decrease monotonically as p rises."""
    severity = {Action.APPROVE: 0, Action.STEP_UP: 1, Action.REVIEW: 2, Action.BLOCK: 3}
    bands = decision_boundaries(AMOUNT, CostModel())
    ranks = [severity[a] for _, _, a in bands]
    assert ranks == sorted(ranks), f"non-monotone policy: {bands}"


def test_boundaries_agree_with_pointwise_decisions():
    costs = CostModel()
    for low, high, action in decision_boundaries(AMOUNT, costs):
        assert decide((low + high) / 2, AMOUNT, costs).action is action


def test_removing_an_action_reshapes_the_policy():
    """A merchant with no analyst team gets boundaries re-derived, not patched."""
    allowed = (Action.APPROVE, Action.BLOCK)
    bands = decision_boundaries(AMOUNT, CostModel(), allowed=allowed)
    assert {a for _, _, a in bands} <= set(allowed)


def _approve_ceiling(amount: float, costs: CostModel) -> float:
    """Highest fraud probability at which approving is still the cheapest action."""
    for low, _high, action in decision_boundaries(amount, costs):
        if action is not Action.APPROVE:
            return low
    return 1.0


def test_flat_dispute_fee_makes_small_tickets_stricter():
    """A result that contradicts the obvious intuition — and is correct.

    "Bigger ticket, be more careful" is the human heuristic, but under expected
    value it does not hold: the goods loss, the false-decline loss and the
    step-up friction all scale with the ticket, so they largely cancel. What does
    NOT scale is the flat dispute fee. On a ₹500 order that fee dwarfs the
    basket and makes approving fraud disproportionately expensive; on a ₹50,000
    order it is rounding. So the approve band is *tighter* on small tickets.

    Worth stating in the write-up: it is the kind of conclusion a cost model
    produces and a hand-tuned threshold table never would.
    """
    costs = CostModel(dispute_fee=850.0)
    assert _approve_ceiling(500.0, costs) < _approve_ceiling(50_000.0, costs)


def test_without_a_flat_fee_ticket_size_barely_matters():
    """Confirms the mechanism above rather than a coincidence of the defaults.

    Remove the fixed fee and every remaining cost is proportional to the ticket,
    so the amount cancels out of the boundary and the policy becomes
    scale-invariant.
    """
    costs = CostModel(dispute_fee=0.0)
    assert _approve_ceiling(500.0, costs) == pytest.approx(
        _approve_ceiling(50_000.0, costs), rel=1e-9
    )


def test_expected_value_is_risk_neutral_by_construction():
    """Documents a real limitation, so it is a choice and not an oversight.

    Expected value treats "lose ₹4,000 with certainty" and "lose ₹400,000 with
    probability 1%" as identical. A merchant does not: the second can be
    existential. Risk aversion has to be expressed through the cost inputs — a
    false_decline_multiplier above 1, or a fee that scales at high tickets — and
    is not something the argmin supplies for free.
    """
    costs = CostModel()
    small = expected_cost(Action.APPROVE, 0.10, 4_000.0, costs)
    large = expected_cost(Action.APPROVE, 0.001, 400_000.0, costs)
    # Comparable expectations, wildly different variance; the policy cannot tell.
    assert small == pytest.approx(485.0, rel=0.05)
    assert large == pytest.approx(400.85, rel=0.05)


def test_sensitivity_sweeps_an_assumption():
    result = sensitivity(AMOUNT, CostModel(), "dispute_fee", [0.0, 850.0, 5_000.0])
    assert [v for v, _ in result] == [0.0, 850.0, 5_000.0]
    assert all(bands for _, bands in result)


def test_sensitivity_rejects_unknown_fields():
    with pytest.raises(AttributeError):
        list(sensitivity(AMOUNT, CostModel(), "not_a_field", [1.0]))


# ---------------------------------------------------------------------------
# VAMP portfolio layer
# ---------------------------------------------------------------------------
def test_thresholds_are_verified_against_visa_fact_sheet():
    """Defaults are sourced from Visa's VAMP fact sheet, effective 1 June 2025."""
    t = ThresholdTable()
    assert t.verified is True
    assert "Visa Acquirer Monitoring Program" in t.source
    # An overridden source that starts with UNVERIFIED must flag as such.
    t2 = ThresholdTable(source="UNVERIFIED — placeholder")
    assert t2.verified is False


def test_bands_classify_by_ratio():
    t = ThresholdTable()
    assert t.band_for(0.0001) is Band.OK
    assert t.band_for(0.0035) is Band.EARLY_WARNING
    assert t.band_for(0.0055) is Band.ABOVE_STANDARD
    assert t.band_for(0.0090) is Band.EXCESSIVE


def test_marginal_dispute_costs_more_near_a_threshold():
    """The core acquirer insight: proximity to a band is itself expensive."""
    calm = PortfolioState(settled_transactions=1_000_000, disputes=1_000)      # 0.10%
    tipping = PortfolioState(settled_transactions=1_000_000, disputes=4_999)   # just under 0.50%
    assert marginal_dispute_cost_inr(tipping) > marginal_dispute_cost_inr(calm)


def test_marginal_cost_is_zero_on_an_empty_book():
    assert marginal_dispute_cost_inr(PortfolioState(0, 0)) == 0.0


def test_headroom_counts_disputes_to_each_band():
    room = headroom(PortfolioState(settled_transactions=100_000, disputes=100))
    assert room["above_standard"] == pytest.approx(0.0050 * 100_000 - 100)
    assert room["excessive"] > room["above_standard"]


def test_big_healthy_merchant_can_outrank_small_hot_one():
    """The case merchant-level monitoring misses.

    The boutique breaches the merchant threshold and the marketplace does not,
    yet the marketplace contributes far more to the acquirer's ratio.
    """
    merchants = [
        MerchantState("tiny-boutique", settled_transactions=1_000, disputes=40),      # 4.0%
        MerchantState("large-marketplace", settled_transactions=900_000, disputes=5_400),  # 0.6%
    ]
    ranked = rank_merchants_by_portfolio_impact(merchants)
    assert ranked[0].merchant_id == "large-marketplace"
    assert ranked[0].merchant_ratio < ranked[1].merchant_ratio


def test_defence_reports_basis_points_not_just_wins():
    portfolio = PortfolioState(settled_transactions=1_000_000, disputes=6_000)  # 0.60%
    proj = project_defence(portfolio, disputes_defended=2_000)
    assert proj.ratio_after < proj.ratio_before
    assert proj.bps_saved == pytest.approx(20.0)


def test_defence_out_of_a_fee_band_avoids_fines():
    portfolio = PortfolioState(settled_transactions=1_000_000, disputes=7_500)  # excessive
    proj = project_defence(portfolio, disputes_defended=4_000)                  # → below above_standard
    assert proj.band_before is Band.EXCESSIVE
    assert proj.band_after in (Band.OK, Band.EARLY_WARNING)
    assert proj.fines_avoided_inr > 0


def test_cannot_defend_more_disputes_than_exist():
    portfolio = PortfolioState(settled_transactions=10_000, disputes=5)
    assert project_defence(portfolio, disputes_defended=999).disputes_defended == 5
