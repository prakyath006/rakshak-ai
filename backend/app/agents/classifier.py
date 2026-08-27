"""Stage 2: Reason Code Classifier.

Maps reason_code to evidence policy deterministically from policies configuration.
"""

import json
from pathlib import Path
from typing import Optional, Dict, Any


class ReasonClassifier:
    """Deterministic classifier mapping chargeback reason codes to evidence policies."""

    def __init__(self, policy_path: Optional[str] = None):
        if policy_path is None:
            policy_path = str(
                Path(__file__).parent.parent / "policies" / "evidence_policies.json"
            )
        
        with open(policy_path, "r", encoding="utf-8") as f:
            self.policies: Dict[str, Any] = json.load(f)

    def classify(self, reason_code: str) -> Dict[str, Any]:
        """Look up evidence policy for given reason code."""
        # Check direct match
        policy = self.policies.get(str(reason_code))
        if policy:
            return {
                "reason_code": str(reason_code),
                "category": policy["category"],
                "network": policy["network"],
                "reason_description": policy["reason_description"],
                "required_evidence": policy["required_evidence"],
            }

        # Fallback general mapping if unknown code
        return {
            "reason_code": str(reason_code),
            "category": "unknown",
            "network": "unknown",
            "reason_description": "Unclassified Dispute Code",
            "required_evidence": [
                {
                    "type": "INVOICE",
                    "razorpay_field": "billing_proof",
                    "critical": true,
                    "weight": 0.5,
                    "description": "Invoice for transaction",
                },
                {
                    "type": "CUSTOMER_COMMUNICATION",
                    "razorpay_field": "customer_communication",
                    "critical": false,
                    "weight": 0.5,
                    "description": "Customer communication logs",
                },
            ],
        }
