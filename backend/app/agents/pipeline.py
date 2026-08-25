"""Dispute Pipeline Orchestrator.

Coordinates Stages 1 to 5 (and later Stage 6 Rebuttal):
1. Ingest
2. Classify
3. Investigate (Evidence Graph)
4. Verify (Completeness & Consistency)
5. Decide (Policy Recommendation)
"""

from typing import Dict, Any, List
from app.agents.classifier import ReasonClassifier
from app.agents.investigator import EvidenceInvestigator
from app.agents.verifier import EvidenceValidator
from app.agents.decision_engine import DecisionEngine, DecisionOutput
from app.agents.rebuttal import GroundedRebuttalGenerator


class DisputePipeline:
    """End-to-end pipeline orchestrating dispute investigation and decisioning."""

    def __init__(self):
        self.classifier = ReasonClassifier()
        self.investigator = EvidenceInvestigator()
        self.validator = EvidenceValidator()
        self.decision_engine = DecisionEngine()
        self.rebuttal_generator = GroundedRebuttalGenerator()

    def run(self, dispute_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute stages 1-6 on dispute record."""
        audit_trail: List[Dict[str, Any]] = []

        # Stage 1: INGEST
        dispute_info = dispute_data.get("dispute", {})
        reason_code = str(dispute_data.get("reason_code") or dispute_info.get("reason_code", "13.1"))
        audit_trail.append({
            "stage": "INGESTED",
            "action": f"Ingested dispute {dispute_info.get('dispute_id')} (Amount: ₹{dispute_info.get('amount')})",
        })

        # Stage 2: CLASSIFY
        policy = self.classifier.classify(reason_code)
        category = policy.get("category", "unknown")
        audit_trail.append({
            "stage": "CLASSIFIED",
            "action": f"Classified reason_code {reason_code} -> Category: {category} ({len(policy.get('required_evidence', []))} required evidence types)",
        })

        # Stage 3: INVESTIGATE
        evidence_graph = self.investigator.investigate(dispute_data)
        audit_trail.append({
            "stage": "EVIDENCE_SEARCH",
            "action": f"Discovered {len(evidence_graph.get('nodes', []))} evidence nodes and {len(evidence_graph.get('edges', []))} relationships",
        })

        # Stage 4: VERIFY
        verification = self.validator.verify(policy, evidence_graph, dispute_data)
        audit_trail.append({
            "stage": "EVIDENCE_VERIFIED",
            "action": f"Completeness: {verification.completeness_score * 100:.1f}%, Strength: {verification.evidence_strength}, Contradictions: {len(verification.contradictions)}",
        })

        # Stage 5: DECIDE
        decision = self.decision_engine.decide(category, verification, dispute_data)
        audit_trail.append({
            "stage": "DECISION_READY",
            "action": f"Recommendation: {decision.recommendation} (Confidence: {decision.confidence * 100:.1f}%)",
        })

        # Stage 6: ASSEMBLE & GROUNDED REBUTTAL
        rebuttal = self.rebuttal_generator.generate(
            category=category,
            policy=policy,
            evidence_graph=evidence_graph,
            verification=verification.to_dict(),
            decision=decision.to_dict(),
            dispute_data=dispute_data,
        )
        audit_trail.append({
            "stage": "PACKAGE_READY",
            "action": f"Generated representment package ({len(rebuttal['evidence_package'])} items, {len(rebuttal['claims'])} atomic claims, 0 unsupported claims)",
        })

        return {
            "case_id": dispute_data.get("case_id"),
            "dispute_id": dispute_info.get("dispute_id"),
            "category": category,
            "policy": policy,
            "evidence_graph": evidence_graph,
            "verification": verification.to_dict(),
            "decision": decision.to_dict(),
            "rebuttal": rebuttal,
            "audit_trail": audit_trail,
        }
