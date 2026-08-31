"""Acquirer-side portfolio risk under Visa's Acquirer Monitoring Program.

WHY AN ACQUIRER CARES MORE THAN A MERCHANT DOES
-----------------------------------------------
VAMP replaced VDMP and VFMP in April 2025 (enforced from October 2025) and
monitors merchants *and acquirers* against dispute-ratio thresholds. The two
tolerances are nothing like each other:

    merchant   flagged "excessive" around 2.2% of transactions
    acquirer   flagged in the region of 0.3%-0.5%, portfolio-wide

An acquirer such as Razorpay is therefore held to a bar several times tighter
than any single merchant on its book, and measured across every merchant at
once. A handful of merchants running hot does not just hurt those merchants — it
drags the whole portfolio toward a band that bills the acquirer per dispute.

That asymmetry is the reason this system exists at the portfolio level and not
just the merchant level: the same dispute is worth far more to prevent when it
lands near an acquirer threshold than when it does not.

IMPORTANT — VERIFY THE NUMBERS BEFORE PUBLISHING
------------------------------------------------
The thresholds and fees below are placeholders taken from secondary reporting,
and sources disagree on the acquirer bands in particular. They MUST be replaced
with figures read from Visa's own VAMP fact sheet before any of this appears in
a submission or a claim. `ThresholdTable.source` records provenance so a stale
default cannot masquerade as a verified figure.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Sequence


class Band(str, Enum):
    """Monitoring band a portfolio or merchant falls into."""

    OK = "OK"
    EARLY_WARNING = "EARLY_WARNING"
    ABOVE_STANDARD = "ABOVE_STANDARD"
    EXCESSIVE = "EXCESSIVE"


@dataclass(frozen=True)
class ThresholdTable:
    """VAMP bands and per-dispute fees.

    Ratios are fractions, not percentages: 0.003 is 0.30%.
    """

    early_warning: float = 0.0030
    above_standard: float = 0.0050
    excessive: float = 0.0070

    fee_above_standard_usd: float = 4.0
    fee_excessive_usd: float = 8.0

    usd_inr: float = 88.0

    source: str = "UNVERIFIED — secondary reporting; replace with Visa VAMP fact sheet"
    """Provenance. Anything other than a citation of Visa's own document means
    these figures are not fit to publish."""

    @property
    def verified(self) -> bool:
        return not self.source.startswith("UNVERIFIED")

    def band_for(self, ratio: float) -> Band:
        if ratio >= self.excessive:
            return Band.EXCESSIVE
        if ratio >= self.above_standard:
            return Band.ABOVE_STANDARD
        if ratio >= self.early_warning:
            return Band.EARLY_WARNING
        return Band.OK

    def fee_inr(self, band: Band) -> float:
        """Fine attracted by each dispute while sitting in `band`."""
        if band is Band.EXCESSIVE:
            return self.fee_excessive_usd * self.usd_inr
        if band is Band.ABOVE_STANDARD:
            return self.fee_above_standard_usd * self.usd_inr
        return 0.0


@dataclass(frozen=True)
class PortfolioState:
    """Where the acquirer's book currently sits in the monitoring window."""

    settled_transactions: int
    disputes: int

    @property
    def ratio(self) -> float:
        if self.settled_transactions <= 0:
            return 0.0
        return self.disputes / self.settled_transactions


@dataclass(frozen=True)
class MerchantState:
    merchant_id: str
    settled_transactions: int
    disputes: int

    @property
    def ratio(self) -> float:
        if self.settled_transactions <= 0:
            return 0.0
        return self.disputes / self.settled_transactions


def marginal_dispute_cost_inr(
    portfolio: PortfolioState,
    thresholds: ThresholdTable = ThresholdTable(),
) -> float:
    """What one *additional* dispute costs the acquirer, in rupees.

    Two components:

      1. The fee on that dispute itself, if the book is already in a fee band.
      2. The step cost when this dispute is the one that tips the portfolio into
         a worse band — at which point every dispute in the window reprices.

    The second term is what makes proximity to a threshold expensive: a book at
    0.49% is far more sensitive to one more dispute than a book at 0.10%, even
    though neither is currently paying a fine. This is the acquirer-side signal
    that a purely merchant-level view cannot see.
    """
    if portfolio.settled_transactions <= 0:
        return 0.0

    before = thresholds.band_for(portfolio.ratio)
    after_state = PortfolioState(portfolio.settled_transactions, portfolio.disputes + 1)
    after = thresholds.band_for(after_state.ratio)

    own_fee = thresholds.fee_inr(after)

    step = 0.0
    if after is not before:
        # Crossing a band reprices every dispute in the monitoring window.
        delta_per_dispute = thresholds.fee_inr(after) - thresholds.fee_inr(before)
        step = delta_per_dispute * portfolio.disputes

    return own_fee + step


def headroom(
    portfolio: PortfolioState,
    thresholds: ThresholdTable = ThresholdTable(),
) -> Dict[str, float]:
    """How many more disputes the book can absorb before each band.

    The number an acquirer risk lead actually wants on a dashboard.
    """
    n = portfolio.settled_transactions
    out: Dict[str, float] = {}
    for name, limit in (
        ("early_warning", thresholds.early_warning),
        ("above_standard", thresholds.above_standard),
        ("excessive", thresholds.excessive),
    ):
        allowed = limit * n
        out[name] = max(0.0, allowed - portfolio.disputes)
    return out


def basis_points(ratio: float) -> float:
    return ratio * 10_000.0


@dataclass
class MerchantContribution:
    merchant_id: str
    disputes: int
    settled_transactions: int
    merchant_ratio: float
    portfolio_bps_contributed: float
    """Basis points this merchant adds to the portfolio ratio. This — not the
    merchant's own ratio — is what decides where defence effort belongs."""

    def __repr__(self) -> str:  # pragma: no cover - display only
        return (
            f"<{self.merchant_id} disputes={self.disputes} "
            f"own={basis_points(self.merchant_ratio):.0f}bps "
            f"contributes={self.portfolio_bps_contributed:.1f}bps>"
        )


def rank_merchants_by_portfolio_impact(
    merchants: Sequence[MerchantState],
) -> List[MerchantContribution]:
    """Order merchants by how much they move the *portfolio* ratio.

    A small merchant at 4% is a compliance problem for itself but barely moves an
    acquirer's book. A large merchant at 0.6% can be the single biggest
    contributor to the portfolio ratio while looking healthy against the merchant
    threshold. Ranking by contributed basis points surfaces the second case,
    which merchant-level monitoring systematically misses.
    """
    total_txns = sum(m.settled_transactions for m in merchants)
    if total_txns <= 0:
        return []

    contributions = [
        MerchantContribution(
            merchant_id=m.merchant_id,
            disputes=m.disputes,
            settled_transactions=m.settled_transactions,
            merchant_ratio=m.ratio,
            portfolio_bps_contributed=basis_points(m.disputes / total_txns),
        )
        for m in merchants
    ]
    contributions.sort(key=lambda c: c.portfolio_bps_contributed, reverse=True)
    return contributions


@dataclass
class DefenceProjection:
    """Effect of successfully defending some number of disputes."""

    disputes_defended: int
    ratio_before: float
    ratio_after: float
    bps_saved: float
    band_before: Band
    band_after: Band
    fines_avoided_inr: float


def project_defence(
    portfolio: PortfolioState,
    disputes_defended: int,
    thresholds: ThresholdTable = ThresholdTable(),
) -> DefenceProjection:
    """What winning `disputes_defended` representments is worth to the acquirer.

    This is the headline the submission should report: not "we won N disputes"
    but "we moved the book N basis points and avoided ₹X of monitoring fees."
    """
    if disputes_defended < 0:
        raise ValueError("disputes_defended must be non-negative")
    defended = min(disputes_defended, portfolio.disputes)

    after = PortfolioState(portfolio.settled_transactions, portfolio.disputes - defended)
    band_before = thresholds.band_for(portfolio.ratio)
    band_after = thresholds.band_for(after.ratio)

    fines_before = thresholds.fee_inr(band_before) * portfolio.disputes
    fines_after = thresholds.fee_inr(band_after) * after.disputes

    return DefenceProjection(
        disputes_defended=defended,
        ratio_before=portfolio.ratio,
        ratio_after=after.ratio,
        bps_saved=basis_points(portfolio.ratio - after.ratio),
        band_before=band_before,
        band_after=band_after,
        fines_avoided_inr=max(0.0, fines_before - fines_after),
    )
