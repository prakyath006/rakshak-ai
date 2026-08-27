"""Stage 5: Policy-Based Decision Engine.

Determines CONTEST, REVIEW, or DO_NOT_CONTEST based on deterministic verification rules.
The LLM does NOT make the decision.
"""

from typing import Dict, Any, List, Optional, Tuple
from app.agents.verifier import VerificationResult


class DecisionOutput:
    def __init__(
        self,
        recommendation: str,  # CONTEST, REVIEW, DO_NOT_CONTEST
        confidence: float,
        evidence_strength: str,
        reasoning: str,
        verification: VerificationResult,
        structured_explanation: Optional[Dict[str, Any]] = None,
    ):
        self.recommendation = recommendation
        self.confidence = round(confidence, 3)
        self.evidence_strength = evidence_strength
        self.reasoning = reasoning
        self.verification = verification
        self.structured_explanation = structured_explanation or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "recommendation": self.recommendation,
            "confidence": self.confidence,
            "evidence_strength": self.evidence_strength,
            "reasoning": self.reasoning,
            "structured_explanation": self.structured_explanation,
            "verification": self.verification.to_dict(),
        }


def apply_extraction_gate(
    decision: DecisionOutput,
    blocking: List[Dict[str, Any]],
) -> Tuple[DecisionOutput, Optional[str]]:
    """Let quote-verified text signals downgrade a decision -- never upgrade one.

    This is the only point where a model influences the outcome, and the
    influence is strictly one-directional: CONTEST may become REVIEW, and
    nothing else changes. A model that hallucinates merchant fault therefore
    costs an unnecessary human review; it can never cause a false contest.
    REVIEW and DO_NOT_CONTEST are already at least as cautious, so they are
    returned untouched.
    """
    if not blocking or decision.recommendation != "CONTEST":
        return decision, None

    quotes = "; ".join(f'"{f["quote"]}" ({f["communication_id"]})' for f in blocking)
    downgraded = DecisionOutput(
        recommendation="REVIEW",
        confidence=0.55,
        evidence_strength=decision.evidence_strength,
        reasoning=(
            "Evidence package met the contest criteria, but merchant-fault language was found "
            f"in verified correspondence: {quotes}. Escalated for human review rather than contested."
        ),
        verification=decision.verification,
        structured_explanation={
            **decision.structured_explanation,
            "downgraded_from": "CONTEST",
            "downgrade_trigger": [f["signal"] for f in blocking],
            "downgrade_quotes": [f["quote"] for f in blocking],
        },
    )
    note = (
        f"CONTEST downgraded to REVIEW — {len(blocking)} verified merchant-fault "
        f"signal(s) found in correspondence the structured rules do not read."
    )
    return downgraded, note


class DecisionEngine:
    """Deterministic policy engine for dispute representment recommendations."""

    def decide(
        self,
        category: str,
        verification: VerificationResult,
        dispute_data: Dict[str, Any],
    ) -> DecisionOutput:
        # Build structured explanation early so ALL paths return it
        structured_exp = self._build_explanation(category, verification, dispute_data)

        # Category Rule 1: Fraud / Unauthorized cases are strictly human-gated
        if category == "unauthorized_fraud":
            if verification.completeness_score >= 0.80 and verification.consistency_score >= 0.85:
                return DecisionOutput(
                    recommendation="REVIEW",
                    confidence=0.85,
                    evidence_strength="HIGH",
                    reasoning="Strong 3DS authentication and delivery records found. Defense ready for human verification before representment.",
                    verification=verification,
                    structured_explanation=structured_exp,
                )
            else:
                return DecisionOutput(
                    recommendation="REVIEW",
                    confidence=0.40,
                    evidence_strength="LOW",
                    reasoning="Unverified card-absent transaction with missing or anomalous signals. Requires manual fraud investigation.",
                    verification=verification,
                    structured_explanation=structured_exp,
                )

        # Rule 2: Explicit contradictions that prove merchant is at fault -> DO_NOT_CONTEST
        for contra in verification.contradictions:
            if (
                "lost in outbound email" in contra
                or "promised refund" in contra
                or "differs from catalog" in contra
                or "never shipped, but refund was not issued" in contra
            ):
                return DecisionOutput(
                    recommendation="DO_NOT_CONTEST",
                    confidence=0.92,
                    evidence_strength="LOW",
                    reasoning=f"Merchant evidence supports customer claim ({contra}). Submitting contest is not defensible.",
                    verification=verification,
                    structured_explanation=structured_exp,
                )
            if "cancelled order BEFORE shipment" in contra:
                return DecisionOutput(
                    recommendation="DO_NOT_CONTEST",
                    confidence=0.90,
                    evidence_strength="LOW",
                    reasoning=f"Order was cancelled within policy window before dispatch. Merchant was at fault.",
                    verification=verification,
                    structured_explanation=structured_exp,
                )

        # Rule 3: Missing critical evidence -> Escalation to HUMAN REVIEW
        if verification.missing_critical:
            missing_names = ", ".join(verification.missing_critical)
            return DecisionOutput(
                recommendation="REVIEW",
                confidence=0.45,
                evidence_strength="LOW",
                reasoning=f"Critical evidence missing: [{missing_names}]. Automatic representment would likely result in dispute loss.",
                verification=verification,
                structured_explanation=structured_exp,
            )

        # Rule 4: Contradictions / partial issues -> Escalation to HUMAN REVIEW
        if verification.contradictions:
            contra_summary = "; ".join(verification.contradictions)
            return DecisionOutput(
                recommendation="REVIEW",
                confidence=0.60,
                evidence_strength="MEDIUM",
                reasoning=f"Evidence conflict detected: {contra_summary}. Manual review required.",
                verification=verification,
                structured_explanation=structured_exp,
            )


        # Rule 5: CONTEST Criteria
        if (
            not verification.missing_critical
            and not verification.contradictions
            and verification.consistency_score >= 0.85
            and verification.relevance_score >= 0.90
            and verification.completeness_score >= 0.70
        ):
            # Special check for credit_not_processed: must have REFUND_CONFIRMATION
            if category == "credit_not_processed" and "REFUND_CONFIRMATION" not in verification.available_evidence:
                return DecisionOutput(
                    recommendation="REVIEW",
                    confidence=0.50,
                    evidence_strength="LOW",
                    reasoning="Refund confirmation record not verified. Cannot auto-contest without bank credit proof.",
                    verification=verification,
                    structured_explanation=structured_exp,
                )

            # Special check for goods_not_received: must have DELIVERY_CONFIRMATION
            if category == "goods_not_received" and "DELIVERY_CONFIRMATION" not in verification.available_evidence:
                return DecisionOutput(
                    recommendation="REVIEW",
                    confidence=0.45,
                    evidence_strength="LOW",
                    reasoning="Carrier delivery confirmation missing. Automatic representment would likely result in dispute loss.",
                    verification=verification,
                    structured_explanation=structured_exp,
                )

            return DecisionOutput(
                recommendation="CONTEST",
                confidence=0.95,
                evidence_strength="HIGH",
                reasoning="Verified defensible evidence package meeting all critical policy criteria with zero contradictions.",
                verification=verification,
                structured_explanation=structured_exp,
            )

        # Rule 6: Moderate completeness without critical gaps
        if verification.completeness_score >= 0.50 and not verification.missing_critical:
            return DecisionOutput(
                recommendation="REVIEW",
                confidence=0.65,
                evidence_strength="MEDIUM",
                reasoning="Moderate evidence coverage available without fatal contradictions. Analyst review recommended.",
                verification=verification,
                structured_explanation=structured_exp,
            )

        # Default fallback: REVIEW (Safe escalation)
        return DecisionOutput(
            recommendation="REVIEW",
            confidence=0.50,
            evidence_strength="LOW",
            reasoning="Insufficient verified evidence to contest. Manual evaluation recommended.",
            verification=verification,
            structured_explanation=structured_exp,
        )

    def _build_explanation(
        self,
        category: str,
        verification: VerificationResult,
        dispute_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        key_findings = []
        if "DELIVERY_CONFIRMATION" in verification.available_evidence:
            key_findings.append("Carrier delivery confirmation verified at cardholder address.")
        if "REFUND_CONFIRMATION" in verification.available_evidence:
            key_findings.append("Full credit reversal transaction confirmed in payment rails.")
        if "INVOICE" in verification.available_evidence:
            key_findings.append("Tax invoice and itemized purchase order verified.")
        if "PRODUCT_SPECIFICATION" in verification.available_evidence:
            key_findings.append("Catalog listing matches fulfilled item specifications.")

        safety_checks = {
            "cross_order_contamination": "PASS" if not verification.relevance_warnings else "FLAGGED",
            "amount_consistency": "PASS" if verification.consistency_score >= 0.80 else "WARNING",
            "timeline_consistency": "PASS" if not any("Temporal" in c or "AFTER" in c for c in verification.contradictions) else "FLAGGED",
            "source_reliability": f"PASS ({(verification.reliability_score * 100):.1f}%)" if verification.reliability_score >= 0.85 else "LOW",
        }

        return {
            "key_findings": key_findings,
            "missing_critical": verification.missing_critical,
            "missing_optional": verification.missing_optional,
            "contradictions": verification.contradictions,
            "safety_checks": safety_checks,
        }
