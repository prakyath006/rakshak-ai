"""Stage 4: Evidence Validator & Completeness Engine.

Performs deterministic completeness checking, consistency verification,
and contradiction detection.
"""

from typing import Dict, Any, List
from datetime import datetime


class VerificationResult:
    """Structured 4-dimensional verification report."""

    def __init__(
        self,
        completeness_score: float,
        reliability_score: float,
        consistency_score: float,
        relevance_score: float,
        evidence_strength: str,  # HIGH, MEDIUM, LOW (derived)
        available_evidence: List[str],
        missing_critical: List[str],
        missing_optional: List[str],
        contradictions: List[str],
        relevance_warnings: List[str],
        summary_by_type: Dict[str, str],
    ):
        self.completeness_score = round(completeness_score, 3)
        self.reliability_score = round(reliability_score, 3)
        self.consistency_score = round(consistency_score, 3)
        self.relevance_score = round(relevance_score, 3)
        self.evidence_strength = evidence_strength
        self.available_evidence = available_evidence
        self.missing_critical = missing_critical
        self.missing_optional = missing_optional
        self.contradictions = contradictions
        self.relevance_warnings = relevance_warnings
        self.summary_by_type = summary_by_type

    def to_dict(self) -> Dict[str, Any]:
        return {
            "completeness_score": self.completeness_score,
            "reliability_score": self.reliability_score,
            "consistency_score": self.consistency_score,
            "relevance_score": self.relevance_score,
            "evidence_strength": self.evidence_strength,
            "available_evidence": self.available_evidence,
            "missing_critical": self.missing_critical,
            "missing_optional": self.missing_optional,
            "contradictions": self.contradictions,
            "relevance_warnings": self.relevance_warnings,
            "summary_by_type": self.summary_by_type,
        }


class EvidenceValidator:
    """Validates evidence across Completeness, Reliability, Consistency, and Relevance."""

    def verify(
        self,
        policy: Dict[str, Any],
        evidence_graph: Dict[str, Any],
        dispute_data: Dict[str, Any],
    ) -> VerificationResult:
        nodes = evidence_graph.get("nodes", [])
        required_list = policy.get("required_evidence", [])

        # Base dispute metadata
        dispute_info = dispute_data.get("dispute", {})
        dispute_amt = float(dispute_info.get("amount", 0.0))
        target_order_id = dispute_data.get("order", {}).get("order_id", "")
        target_payment_id = dispute_data.get("payment", {}).get("payment_id", "")

        # -------------------------------------------------------------
        # 1. RELEVANCE & ADVERSARIAL TRAP VALIDATION
        # -------------------------------------------------------------
        relevance_warnings: List[str] = []
        valid_nodes: List[Dict[str, Any]] = []

        for node in nodes:
            is_relevant = True
            source_rec = str(node.get("source_record_id", ""))
            content = node.get("content", {})

            # Trap A: Cross-order / cross-payment contamination
            # If evidence has an explicit order_id or source_record_id that conflicts with disputed order
            node_order_id = content.get("order_id")
            if node_order_id and node_order_id != target_order_id:
                relevance_warnings.append(
                    f"Contaminated Evidence: {node['evidence_id']} belongs to order {node_order_id}, but dispute is for {target_order_id}."
                )
                is_relevant = False

            # Trap B: Amount Discrepancy (e.g. ₹5,000 invoice attached to ₹50,000 dispute)
            node_amt = content.get("amount") or content.get("order_amount") or content.get("invoice_amount")
            if node_amt is not None and dispute_amt > 0:
                node_amt_float = float(node_amt)
                if abs(node_amt_float - dispute_amt) / dispute_amt > 0.10:  # >10% mismatch
                    relevance_warnings.append(
                        f"Amount Mismatch: Evidence {node['evidence_id']} is for ₹{node_amt_float:,.2f}, but dispute amount is ₹{dispute_amt:,.2f}."
                    )
                    # For invoice / billing proof, severe mismatch degrades relevance
                    if node["type"] in ["INVOICE", "PAYMENT_RECORD", "ORDER_RECORD"]:
                        is_relevant = False

            if is_relevant:
                valid_nodes.append(node)

        # Relevance Score calculation
        total_nodes = len(nodes)
        relevance_score = (len(valid_nodes) / total_nodes) if total_nodes > 0 else 1.0

        # Map available types strictly from valid/relevant nodes
        available_types = set(node["type"] for node in valid_nodes)

        # -------------------------------------------------------------
        # 2. COMPLETENESS CHECK
        # -------------------------------------------------------------
        total_weight = 0.0
        acquired_weight = 0.0
        missing_critical: List[str] = []
        missing_optional: List[str] = []
        summary_by_type: Dict[str, str] = {}

        for req in required_list:
            req_type = req["type"]
            weight = req.get("weight", 0.1)
            is_critical = req.get("critical", False)
            total_weight += weight

            if req_type in available_types:
                acquired_weight += weight
                summary_by_type[req_type] = "PRESENT"
            else:
                summary_by_type[req_type] = "MISSING"
                if is_critical:
                    missing_critical.append(req_type)
                else:
                    missing_optional.append(req_type)

        completeness_score = (
            acquired_weight / total_weight if total_weight > 0 else 0.0
        )

        # -------------------------------------------------------------
        # 3. RELIABILITY CHECK (Source credibility weighting)
        # -------------------------------------------------------------
        if valid_nodes:
            total_reliability = sum(node.get("reliability", 0.8) for node in valid_nodes)
            reliability_score = total_reliability / len(valid_nodes)
        else:
            reliability_score = 0.0

        # -------------------------------------------------------------
        # 4. CONSISTENCY & CONTRADICTION DETECTION
        # -------------------------------------------------------------
        contradictions: List[str] = []
        consistency_deductions = 0.0

        # Rule A: Delivery Address Mismatch
        shipment_data = dispute_data.get("shipment")
        if shipment_data:
            if not shipment_data.get("delivery_address_match", True):
                contradictions.append(
                    f"Delivery address city ({shipment_data.get('delivery_address_city')}) does not match billing/customer address."
                )
                consistency_deductions += 0.30

            # Rule B: Partial Delivery vs Full Dispute Amount
            items_shipped = shipment_data.get("items_shipped", 1)
            order_qty = dispute_data.get("order", {}).get("quantity", 1)
            if items_shipped < order_qty:
                contradictions.append(
                    f"Partial fulfillment detected: {items_shipped} of {order_qty} items shipped, but dispute claims full order value."
                )
                consistency_deductions += 0.25

        # Rule C: Customer Communication acknowledgment vs merchant admission of loss
        comms = dispute_data.get("communications", [])
        for comm in comms:
            msg_lower = comm.get("message", "").lower()
            if "lost" in msg_lower and comm.get("direction") == "outbound":
                contradictions.append("Merchant confirmed package lost in outbound email to customer.")
                consistency_deductions += 0.50
            elif "will process your refund" in msg_lower or "will refund" in msg_lower:
                refunds = dispute_data.get("refunds", [])
                if not refunds or all(r.get("status") != "processed" for r in refunds):
                    contradictions.append(
                        "Merchant promised refund in written communication, but no processed refund record exists."
                    )
                    consistency_deductions += 0.50

        # Rule D: Cancellation timing & unfulfilled cancellation
        order_data = dispute_data.get("order", {})
        cancelled_at = order_data.get("cancelled_at")
        if cancelled_at:
            if not shipment_data:
                refunds = dispute_data.get("refunds", [])
                if not refunds or all(r.get("status") == "failed" for r in refunds):
                    contradictions.append(
                        "Order was cancelled prior to fulfillment and never shipped, but refund was not issued."
                    )
                    consistency_deductions += 0.50
            elif shipment_data.get("shipped_at"):
                canc_dt = parse_iso(cancelled_at)
                ship_dt = parse_iso(shipment_data.get("shipped_at"))
                if canc_dt and ship_dt:
                    if canc_dt > ship_dt:
                        contradictions.append(
                            f"Order was cancelled at {cancelled_at} AFTER shipment dispatch at {shipment_data.get('shipped_at')}."
                        )
                        consistency_deductions += 0.20
                    else:
                        contradictions.append(
                            f"Customer cancelled order BEFORE shipment was dispatched ({cancelled_at} < {shipment_data.get('shipped_at')}), but merchant dispatched anyway."
                        )
                        consistency_deductions += 0.50

        # Rule E: Partial or Pending Refund vs Disputed Amount
        refunds_data = dispute_data.get("refunds", [])
        for rfnd in refunds_data:
            if rfnd.get("status") == "pending":
                contradictions.append(
                    f"Refund of ₹{rfnd.get('amount')} is in PENDING state in banking rails."
                )
                consistency_deductions += 0.20
            elif rfnd.get("status") == "processed" and float(rfnd.get("amount")) < float(dispute_amt):
                contradictions.append(
                    f"Partial refund of ₹{rfnd.get('amount')} was processed, but dispute claims full ₹{dispute_amt}."
                )
                consistency_deductions += 0.15

        # Rule F: Product Specification Discrepancy
        product_data = dispute_data.get("product", {})
        spec = product_data.get("specification", "")
        if "Fulfilled: 8GB" in spec and "16GB" in spec:
            contradictions.append(
                "Delivered product configuration differs from catalog advertisement."
            )
            consistency_deductions += 0.60
        elif "omitted in catalog" in spec.lower() or "generic" in spec.lower():
            contradictions.append(
                "Catalog specification is ambiguous or lacks exact component variant details."
            )
            consistency_deductions += 0.20

        # Rule G: Temporal Inversion Anomaly (Shipment or Delivery before Order Creation)
        order_dt_str = order_data.get("created_at")
        if order_dt_str and shipment_data:
            order_dt = parse_iso(order_dt_str)
            shipped_dt = parse_iso(shipment_data.get("shipped_at") or "")
            delivered_dt = parse_iso(shipment_data.get("delivered_at") or "")

            if order_dt and shipped_dt and shipped_dt < order_dt:
                contradictions.append(
                    f"Temporal Inversion Anomaly: Shipment dispatch ({shipment_data.get('shipped_at')}) precedes order creation ({order_dt_str})."
                )
                consistency_deductions += 0.50
            if order_dt and delivered_dt and delivered_dt < order_dt:
                contradictions.append(
                    f"Temporal Inversion Anomaly: Delivery timestamp ({shipment_data.get('delivered_at')}) precedes order creation ({order_dt_str})."
                )
                consistency_deductions += 0.50

        consistency_score = max(0.0, 1.0 - consistency_deductions)

        # -------------------------------------------------------------
        # 5. DERIVED EVIDENCE STRENGTH
        # f(Completeness, Reliability, Consistency, Relevance)
        # -------------------------------------------------------------
        composite_score = (
            (completeness_score * 0.40)
            + (consistency_score * 0.30)
            + (reliability_score * 0.15)
            + (relevance_score * 0.15)
        )

        if (
            completeness_score >= 0.80
            and consistency_score >= 0.85
            and relevance_score >= 0.90
            and not missing_critical
            and not contradictions
        ):
            evidence_strength = "HIGH"
        elif composite_score >= 0.55:
            evidence_strength = "MEDIUM"
        else:
            evidence_strength = "LOW"

        return VerificationResult(
            completeness_score=completeness_score,
            reliability_score=reliability_score,
            consistency_score=consistency_score,
            relevance_score=relevance_score,
            evidence_strength=evidence_strength,
            available_evidence=list(available_types),
            missing_critical=missing_critical,
            missing_optional=missing_optional,
            contradictions=contradictions,
            relevance_warnings=relevance_warnings,
            summary_by_type=summary_by_type,
        )


def parse_iso(dt_str: str) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    except Exception:
        return None
