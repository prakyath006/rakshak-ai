"""Acquirer-side portfolio risk under Visa's Acquirer Monitoring Program.

WHY AN ACQUIRER CARES MORE THAN A MERCHANT DOES
-----------------------------------------------
VAMP replaced VDMP and VFMP in April 2025 (enforced from October 2025) and
monitors merchants *and acquirers* against dispute-ratio thresholds. The two
tolerances are nothing like each other:

    merchant   flagged "excessive" at >= 220 bps (2.20%)
    acquirer   Above Standard at >= 50 bps, Excessive at >= 70 bps, portfolio-wide

Source: Visa Acquirer Monitoring Program Overview fact sheet, effective 1 June 2025.
URL: https://corporate.visa.com/content/dam/VCOM/corporate/visa-perspectives/
     security-and-trust/documents/visa-acquirer-monitoring-program-fact-sheet-2025.pdf

An acquirer such as Razorpay is therefore held to a bar roughly three times
tighter than any single merchant on its book, and measured across every merchant
at once. A handful of merchants running hot does not just hurt those merchants — it
drags the whole portfolio toward a band that bills the acquirer per dispute.

That asymmetry is the reason this system exists at the portfolio level and not
just the merchant level: the same dispute is worth far more to prevent when it
lands near an acquirer threshold than when it does not.

INDIA-SPECIFIC NOTE
-------------------
The fact sheet states: "Programs for Brazil, Chile, and India will be announced
later." India is not yet under VAMP as of September 2026. However, the
underlying economics — per-dispute fines at acquirer-level thresholds — are the
standard Visa enforcement pattern globally, and India's programme is expected to
follow with the same or similar thresholds. The architecture is built for that
eventuality.

FEES
----
The per-dispute fees ($4 Above Standard, $8 Excessive) are from Visa's published
fee schedule, not from this specific fact sheet. They are marked as such in the
source string.
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

    # Acquirer portfolio thresholds — verified against Visa VAMP fact sheet.
    # "An acquirer's portfolio is identified as Above Standard if its VAMP ratio
    #  is >=50bps and as Excessive if >=70bps" — verbatim from the document.
    early_warning: float = 0.0030
    above_standard: float = 0.0050  # >= 50 bps
    excessive: float = 0.0070       # >= 70 bps

    # Merchant excessive (AP/Canada/EU/US): >= 220 bps, with >= 1,500 monthly
    # fraud+disputes. Reduces to >= 150 bps in those regions from 1 April 2026.
    merchant_excessive: float = 0.0220  # 220 bps
    merchant_min_monthly_count: int = 1500

    # Per-dispute fees — from Visa's published fee schedule, not this fact sheet.
    fee_above_standard_usd: float = 4.0
    fee_excessive_usd: float = 8.0

    usd_inr: float = 88.0

    source: str = (
        "Verified — Visa Acquirer Monitoring Program Overview fact sheet, "
        "effective 1 June 2025. Thresholds: acquirer Above Standard >= 50 bps, "
        "Excessive >= 70 bps; merchant Excessive >= 220 bps (AP/CA/EU/US). "
        "Fees from Visa fee schedule (not this fact sheet). "
        "India programme not yet announced per footnote 1."
    )
    """Provenance. Starts with 'Verified' when sourced from Visa's own document."""

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
