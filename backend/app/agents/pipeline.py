"""Dispute Pipeline Orchestrator.

Stages:
1. Ingest
2. Classify
3. Investigate (Evidence Graph)
3.5 Extract (LLM reading of unstructured text -- inert when LLM_PROVIDER=none)
4. Verify (Completeness & Consistency)
5. Decide (deterministic policy recommendation)
5.5 Safety gate (extraction may only downgrade a decision toward review)
6. Assemble grounded representment package
"""

from typing import Dict, Any, List

from app.agents.classifier import ReasonClassifier
from app.agents.investigator import EvidenceInvestigator
from app.agents.verifier import EvidenceValidator
from app.agents.decision_engine import DecisionEngine, DecisionOutput, apply_extraction_gate
from app.agents.rebuttal import GroundedRebuttalGenerator
from app.agents.extractor import EvidenceExtractor, blocking_flags
from app.services.llm import LLMClient


class DisputePipeline:
    """End-to-end pipeline orchestrating dispute investigation and decisioning."""

    def __init__(self, use_llm: bool = True):
        """`use_llm=False` pins the pipeline to the deterministic path.

        Benchmark and regression scripts pass False deliberately: the suites must
        be reproducible and free of network calls, and a 1,000-case run would
        otherwise fire 1,000 model requests whose output can vary between runs.
        The API server uses the default (True).
        """
        self.use_llm = use_llm
        offline = None if use_llm else LLMClient(provider="none")

        self.classifier = ReasonClassifier()
        self.investigator = EvidenceInvestigator()
        self.extractor = EvidenceExtractor(client=offline)
        self.validator = EvidenceValidator()
        self.decision_engine = DecisionEngine()
        self.rebuttal_generator = GroundedRebuttalGenerator(llm_client=offline)

    def run(self, dispute_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute stages 1-6 on a dispute record."""
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

        # Stage 3.5: EXTRACT unstructured text (no-op when the LLM path is off)
        extraction = self.extractor.extract(dispute_data)
        audit_trail.append({
            "stage": "TEXT_EXTRACTION",
            "action": self._describe_extraction(extraction),
        })

        # Stage 4: VERIFY
        verification = self.validator.verify(policy, evidence_graph, dispute_data)
        audit_trail.append({
            "stage": "EVIDENCE_VERIFIED",
            "action": f"Completeness: {verification.completeness_score * 100:.1f}%, Strength: {verification.evidence_strength}, Contradictions: {len(verification.contradictions)}",
        })

        # Stage 5: DECIDE (deterministic -- the model has no vote here)
        decision = self.decision_engine.decide(category, verification, dispute_data)
        audit_trail.append({
            "stage": "DECISION_READY",
            "action": f"Recommendation: {decision.recommendation} (Confidence: {decision.confidence * 100:.1f}%)",
        })

        # Stage 5.5: SAFETY GATE -- extraction may only move toward caution
        decision, gate_note = apply_extraction_gate(decision, blocking_flags(extraction))
        if gate_note:
            audit_trail.append({"stage": "SAFETY_GATE", "action": gate_note})

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
            "action": (
                f"Generated representment package ({len(rebuttal['evidence_package'])} items, "
                f"{len(rebuttal['claims'])} atomic claims, "
                f"{rebuttal.get('unsupported_claims_count', 0)} unsupported)"
            ),
        })

        return {
            "case_id": dispute_data.get("case_id"),
            "dispute_id": dispute_info.get("dispute_id"),
            "category": category,
            "policy": policy,
            "evidence_graph": evidence_graph,
            "extraction": extraction,
            "verification": verification.to_dict(),
            "decision": decision.to_dict(),
            "rebuttal": rebuttal,
            "audit_trail": audit_trail,
        }

    @staticmethod
    def _describe_extraction(extraction: Dict[str, Any]) -> str:
        if not extraction.get("enabled"):
            return f"Skipped — {extraction.get('reason')}"
        qv = extraction.get("quote_verification", {})
        if not qv.get("proposed"):
            return "Model read the correspondence and found no decision-relevant signals."
        return (
            f"Model proposed {qv['proposed']} signal(s) from correspondence; "
            f"{qv['verbatim']} verified verbatim, {qv['rejected']} rejected as ungrounded "
            f"({qv['grounding_rate']}% grounded)."
        )
