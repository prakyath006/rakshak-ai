"""Stage 5: Policy-Based Decision Engine.

Determines CONTEST, REVIEW, or DO_NOT_CONTEST based on deterministic verification rules.
The LLM does NOT make the decision.
"""

from typing import Dict, Any
from app.agents.verifier import VerificationResult


class DecisionOutput:
    def __init__(
        self,
        recommendation: str,  # CONTEST, REVIEW, DO_NOT_CONTEST
        confidence: float,
        evidence_strength: str,
        reasoning: str,
        verification: VerificationResult,
    ):
        self.recommendation = recommendation
        self.confidence = round(confidence, 3)
        self.evidence_strength = evidence_strength
        self.reasoning = reasoning
        self.verification = verification

    def to_dict(self) -> Dict[str, Any]:
        return {
            "recommendation": self.recommendation,
            "confidence": self.confidence,
            "evidence_strength": self.evidence_strength,
            "reasoning": self.reasoning,
            "verification": self.verification.to_dict(),
        }


class DecisionEngine:
    """Deterministic policy engine for dispute representment recommendations."""

    def decide(
        self,
        category: str,
        verification: VerificationResult,
        dispute_data: Dict[str, Any],
    ) -> DecisionOutput:
        # Category Rule 1: Fraud / Unauthorized cases are strictly human-gated
        if category == "unauthorized_fraud":
            if verification.completeness_score >= 0.80 and verification.consistency_score >= 0.85:
                return DecisionOutput(
                    recommendation="REVIEW",
                    confidence=0.85,
                    evidence_strength="HIGH",
                    reasoning="Strong 3DS authentication and delivery records found. Defense ready for human verification before representment.",
                    verification=verification,
                )
            else:
                return DecisionOutput(
                    recommendation="REVIEW",
                    confidence=0.40,
                    evidence_strength="LOW",
                    reasoning="Unverified card-absent transaction with missing or anomalous signals. Requires manual fraud investigation.",
                    verification=verification,
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
                )
            if "cancelled order BEFORE shipment" in contra:
                return DecisionOutput(
                    recommendation="DO_NOT_CONTEST",
                    confidence=0.90,
                    evidence_strength="LOW",
                    reasoning=f"Order was cancelled within policy window before dispatch. Merchant was at fault.",
                    verification=verification,
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
            )

        # Rule 5: High completeness & High consistency -> CONTEST
        if (
            verification.completeness_score >= 0.80
            and verification.consistency_score >= 0.85
            and not verification.missing_critical
        ):
            return DecisionOutput(
                recommendation="CONTEST",
                confidence=0.95,
                evidence_strength="HIGH",
                reasoning="Complete and consistent evidence package verified against card-network dispute policy. Case is strongly defensible.",
                verification=verification,
            )

        # Rule 6: Moderate completeness without critical gaps
        if verification.completeness_score >= 0.50:
            return DecisionOutput(
                recommendation="REVIEW",
                confidence=0.65,
                evidence_strength="MEDIUM",
                reasoning="Moderate evidence coverage available. Review evidence package before submission.",
                verification=verification,
            )

        # Default fallback: REVIEW
        return DecisionOutput(
            recommendation="REVIEW",
            confidence=0.50,
            evidence_strength="LOW",
            reasoning="Insufficient verified evidence to contest. Manual evaluation recommended.",
            verification=verification,
        )
