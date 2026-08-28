"""Stage 6: Grounded Rebuttal Generator & Anti-Hallucination Verification Layer.

Two narrative paths:

  TEMPLATE (always available)
      Deterministic f-strings built directly from evidence nodes. Safe, but the
      claim check over it is close to a tautology: the claims are constructed
      from the same dicts they cite, so they cannot fail to be grounded. That
      number is reported as `structurally_guaranteed: true` rather than being
      passed off as a hallucination measurement.

  LLM DRAFT (when LLM_PROVIDER is configured)
      A model writes the representment from the evidence graph. This *can*
      hallucinate -- invented tracking numbers, wrong amounts, dates that were
      never in the record -- so every factual token in the draft is checked
      against the evidence before the draft is allowed anywhere near a
      submission. A draft that fails is discarded and the template is used, and
      the rejection is reported rather than hidden.
"""

from typing import Dict, Any, List, Optional, Set, Tuple
import json
import re

from app.services.llm import LLMClient, LLMError, get_llm_client

# Tokens worth checking: currency amounts, ISO-ish dates, and identifiers that
# mix letters and digits (tracking numbers, order/payment/evidence IDs).
_AMOUNT_RE = re.compile(r"(?<![\w.])\d{1,3}(?:,\d{2,3})*(?:\.\d{2})?(?![\w])")
_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2})?)?")
_IDENT_RE = re.compile(r"\b(?=[A-Za-z0-9_-]*\d)[A-Za-z][A-Za-z0-9_-]{4,}\b")

DRAFT_SYSTEM_PROMPT = """You draft chargeback representment narratives for a merchant.

You are given a set of verified evidence items. Write a short, factual representment addressed to the issuing bank.

ABSOLUTE RULES:
1. Use ONLY facts present in the evidence items given to you. Invent nothing.
2. Never state a date, amount, tracking number, carrier, or identifier that does not appear verbatim in the evidence.
3. Cite the evidence id in square brackets immediately after each factual claim, e.g. "delivered on 2026-08-22 [EV-DEL-001]".
4. If the evidence does not support a point, omit the point. Do not hedge, speculate, or fill gaps.
5. Three or four sentences. Plain professional English. No greeting, no sign-off, no markdown.

Return ONLY a JSON object:
{"narrative": "<the representment text with [EV-...] citations>"}"""


class ClaimVerificationReport:
    """Detailed audit report on claim-level groundedness."""

    def __init__(
        self,
        claims: List[Dict[str, Any]],
        grounded_claims: int,
        total_claims: int,
        grounded_rate: float,
        hallucination_warnings: List[str],
    ):
        self.claims = claims
        self.grounded_claims = grounded_claims
        self.total_claims = total_claims
        self.grounded_rate = round(grounded_rate, 3)
        self.hallucination_warnings = hallucination_warnings

    def to_dict(self) -> Dict[str, Any]:
        return {
            "claims": self.claims,
            "grounded_claims": self.grounded_claims,
            "total_claims": self.total_claims,
            "grounded_rate": self.grounded_rate,
            "hallucination_warnings": self.hallucination_warnings,
        }


def _evidence_token_pool(nodes: List[Dict[str, Any]], dispute_data: Dict[str, Any]) -> Set[str]:
    """Every factual token that legitimately appears in the record.

    Amounts are normalised (commas and trailing .00 stripped) so "48,000.00" in a
    draft matches 48000.0 in the source data.
    """
    blob = json.dumps({"nodes": nodes, "case": dispute_data}, default=str)
    pool: Set[str] = set()

    for match in _AMOUNT_RE.findall(blob):
        pool.add(_normalize_amount(match))
    for match in _DATE_RE.findall(blob):
        pool.add(match[:10])  # date precision is enough; times get reformatted
    for match in _IDENT_RE.findall(blob):
        pool.add(match.lower())

    # Raw numeric forms as they appear in the JSON (e.g. 48000.0 -> "48000")
    for raw in re.findall(r"\d+(?:\.\d+)?", blob):
        pool.add(_normalize_amount(raw))

    return pool


def _normalize_amount(text: str) -> str:
    cleaned = text.replace(",", "")
    try:
        value = float(cleaned)
    except ValueError:
        return cleaned
    return str(int(value)) if value == int(value) else str(value)


def verify_draft_against_evidence(
    draft: str,
    nodes: List[Dict[str, Any]],
    dispute_data: Dict[str, Any],
) -> Dict[str, Any]:
    """Check every factual token in a model-written draft against the evidence.

    Unlike the template claim check, this can fail -- and it is the only thing
    standing between a hallucinated tracking number and a bank submission.
    """
    pool = _evidence_token_pool(nodes, dispute_data)
    node_ids = {n["evidence_id"] for n in nodes}
    unsupported: List[Dict[str, str]] = []
    checked = 0

    # Cited evidence ids must exist.
    for cited in re.findall(r"\[([A-Za-z0-9_-]+)\]", draft):
        checked += 1
        if cited not in node_ids:
            unsupported.append({"token": cited, "kind": "citation", "detail": "No such evidence node."})

    body = re.sub(r"\[[A-Za-z0-9_-]+\]", " ", draft)  # citations already checked

    for amount in _AMOUNT_RE.findall(body):
        normalized = _normalize_amount(amount)
        if len(normalized) < 3:
            continue  # skip small counts like "1 item" / "3 days"
        checked += 1
        if normalized not in pool:
            unsupported.append({"token": amount, "kind": "amount", "detail": "Not present in the evidence record."})

    for date in _DATE_RE.findall(body):
        checked += 1
        if date[:10] not in pool:
            unsupported.append({"token": date, "kind": "date", "detail": "Not present in the evidence record."})

    for ident in _IDENT_RE.findall(body):
        checked += 1
        if ident.lower() not in pool:
            unsupported.append({"token": ident, "kind": "identifier", "detail": "Not present in the evidence record."})

    return {
        "tokens_checked": checked,
        "unsupported": unsupported,
        "passed": not unsupported,
        "grounding_rate": round((checked - len(unsupported)) / checked * 100, 2) if checked else None,
    }


class GroundedRebuttalGenerator:
    """Generates representment narrative grounded strictly in verified evidence nodes."""

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm = llm_client or get_llm_client()

    def _draft_with_llm(
        self,
        nodes: List[Dict[str, Any]],
        dispute_data: Dict[str, Any],
    ) -> Tuple[Optional[str], Dict[str, Any]]:
        """Return (narrative, report). narrative is None when the draft is unusable."""
        report: Dict[str, Any] = {
            "attempted": False,
            "accepted": False,
            "model": self.llm.model,
            "reason": None,
            "verification": None,
            "rejected_draft": None,
        }

        if not self.llm.is_enabled:
            report["reason"] = self.llm.disabled_reason()
            return None, report

        report["attempted"] = True
        evidence_view = [
            {
                "evidence_id": n["evidence_id"],
                "type": n["type"],
                "source": n["source"],
                "timestamp": n.get("timestamp"),
                "content": n.get("content", {}),
            }
            for n in nodes
        ]

        try:
            raw = self.llm.complete_json(
                system=DRAFT_SYSTEM_PROMPT,
                user=(
                    f"Dispute reason: {dispute_data.get('reason_description', 'unspecified')}\n"
                    f"Cardholder's claim: {dispute_data.get('dispute', {}).get('customer_claim_text', 'n/a')}\n\n"
                    f"Verified evidence:\n{json.dumps(evidence_view, indent=2, default=str)}"
                ),
                max_tokens=900,
            )
        except LLMError as exc:
            report["reason"] = f"Draft call failed ({exc}). Template narrative used."
            return None, report

        narrative = (raw.get("narrative") or "").strip()
        if not narrative:
            report["reason"] = "Model returned an empty narrative. Template narrative used."
            return None, report

        verification = verify_draft_against_evidence(narrative, nodes, dispute_data)
        report["verification"] = verification

        if not verification["passed"]:
            report["reason"] = (
                f"Draft rejected: {len(verification['unsupported'])} unsupported token(s) "
                f"({', '.join(u['token'] for u in verification['unsupported'][:5])}). Template narrative used."
            )
            report["rejected_draft"] = narrative
            return None, report

        report["accepted"] = True
        report["reason"] = "Draft passed token-level grounding checks against the evidence graph."
        return narrative, report

    def generate(
        self,
        category: str,
        policy: Dict[str, Any],
        evidence_graph: Dict[str, Any],
        verification: Dict[str, Any],
        decision: Dict[str, Any],
        dispute_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        nodes = evidence_graph.get("nodes", [])
        nodes_by_type = {node["type"]: node for node in nodes}
        nodes_by_id = {node["evidence_id"]: node for node in nodes}

        order_data = dispute_data.get("order", {})
        customer_data = dispute_data.get("customer", {})
        product_data = dispute_data.get("product", {})
        shipment_data = dispute_data.get("shipment", {})
        payment_data = dispute_data.get("payment", {})

        recommendation = decision.get("recommendation", "REVIEW")
        paragraphs: List[str] = []
        structured_claims: List[Dict[str, Any]] = []

        # -------------------------------------------------------------
        # 1. GROUNDED NARRATIVE GENERATION (Contest vs Review vs Do Not Contest)
        # -------------------------------------------------------------
        if recommendation == "CONTEST":
            if category == "goods_not_received":
                del_node = nodes_by_type.get("DELIVERY_CONFIRMATION")
                ship_node = nodes_by_type.get("SHIPPING_PROOF")
                inv_node = nodes_by_type.get("INVOICE")
                comm_node = nodes_by_type.get("CUSTOMER_COMMUNICATION")

                # Claim 1: Purchase and invoice
                if inv_node:
                    c1_text = f"The disputed order (Order ID: {order_data.get('order_id')}) for amount INR {payment_data.get('amount'):,.2f} was legitimately placed and invoiced [{inv_node['evidence_id']}]."
                    paragraphs.append(c1_text)
                    structured_claims.append({
                        "claim": f"Order {order_data.get('order_id')} invoiced for amount INR {payment_data.get('amount'):,.2f}",
                        "evidence_ids": [inv_node["evidence_id"]],
                        "confidence": 0.99,
                    })

                # Claim 2: Fulfillment and delivery
                if ship_node and del_node:
                    carrier = ship_node["content"].get("carrier", "carrier")
                    tracking = ship_node["content"].get("tracking_number", "")
                    shipped_at = ship_node.get("timestamp") or "verified dispatch date"
                    delivered_at = del_node.get("timestamp") or "verified delivery date"

                    c2_text = f"Shipment was dispatched via {carrier} (Tracking: {tracking}) on {shipped_at} [{ship_node['evidence_id']}], and successfully delivered on {delivered_at} to cardholder address [{del_node['evidence_id']}]."
                    paragraphs.append(c2_text)
                    structured_claims.append({
                        "claim": f"Dispatched via {carrier} (Tracking: {tracking}) on {shipped_at}",
                        "evidence_ids": [ship_node["evidence_id"]],
                        "confidence": 0.98,
                    })
                    structured_claims.append({
                        "claim": f"Confirmed delivery on {delivered_at}",
                        "evidence_ids": [del_node["evidence_id"]],
                        "confidence": 0.98,
                    })

                # Claim 3: Customer written acknowledgment (if present)
                if comm_node and "received" in comm_node["content"].get("message", "").lower():
                    msg_dt = comm_node.get("timestamp") or "subsequent date"
                    c3_text = f"Cardholder explicitly acknowledged receipt in written correspondence on {msg_dt}: \"{comm_node['content'].get('message')}\" [{comm_node['evidence_id']}]."
                    paragraphs.append(c3_text)
                    structured_claims.append({
                        "claim": f"Customer confirmed receipt in email on {msg_dt}",
                        "evidence_ids": [comm_node["evidence_id"]],
                        "confidence": 0.95,
                    })

            elif category == "credit_not_processed":
                rfnd_node = nodes_by_type.get("REFUND_CONFIRMATION")
                pol_node = nodes_by_type.get("REFUND_POLICY")

                if rfnd_node:
                    c1_text = f"The merchant has already processed the full credit reversal for Order {order_data.get('order_id')} in amount INR {payment_data.get('amount'):,.2f} [{rfnd_node['evidence_id']}]."
                    paragraphs.append(c1_text)
                    structured_claims.append({
                        "claim": f"Full refund processed for Order {order_data.get('order_id')} for INR {payment_data.get('amount'):,.2f}",
                        "evidence_ids": [rfnd_node["evidence_id"]],
                        "confidence": 0.99,
                    })

                if pol_node:
                    c2_text = f"The transaction was settled in strict adherence to published refund policy terms [{pol_node['evidence_id']}]. No outstanding merchant balance remains."
                    paragraphs.append(c2_text)
                    structured_claims.append({
                        "claim": "Refund executed in compliance with merchant refund policy",
                        "evidence_ids": [pol_node["evidence_id"]],
                        "confidence": 0.95,
                    })

            elif category == "not_as_described":
                prod_node = nodes_by_type.get("PRODUCT_DESCRIPTION")
                spec_node = nodes_by_type.get("PRODUCT_SPECIFICATION")
                del_node = nodes_by_type.get("DELIVERY_CONFIRMATION")

                c1_text = f"The item fulfilled to the cardholder strictly matches the advertised catalog description"
                c1_evs = []
                if prod_node:
                    c1_text += f" [{prod_node['evidence_id']}]"
                    c1_evs.append(prod_node["evidence_id"])
                if spec_node:
                    c1_text += f" and technical specifications [{spec_node['evidence_id']}]"
                    c1_evs.append(spec_node["evidence_id"])
                c1_text += "."
                paragraphs.append(c1_text)
                structured_claims.append({
                    "claim": "Delivered item corresponds to catalog description and technical specifications",
                    "evidence_ids": c1_evs,
                    "confidence": 0.96,
                })

                if del_node:
                    c2_text = f"Fulfillment was delivered as ordered [{del_node['evidence_id']}]. Customer claim of discrepancy is unsubstantiated by order records."
                    paragraphs.append(c2_text)
                    structured_claims.append({
                        "claim": "Order fulfilled and delivered as specified",
                        "evidence_ids": [del_node["evidence_id"]],
                        "confidence": 0.95,
                    })

        elif recommendation == "DO_NOT_CONTEST":
            contradictions = verification.get("contradictions", [])
            contra_str = "; ".join(contradictions)
            paragraphs.append(
                f"REPRESENTMENT NOT RECOMMENDED: Merchant investigation indicates the dispute claim is valid ({contra_str}). Submitting representment is unsupported by evidence."
            )
            structured_claims.append({
                "claim": f"Merchant records confirm dispute claim validity ({contra_str})",
                "evidence_ids": [],
                "confidence": 0.92,
            })

        else:  # REVIEW
            missing = verification.get("missing_critical", [])
            contradictions = verification.get("contradictions", [])
            p1 = "CASE ESCALATED FOR HUMAN REVIEW: "
            reasons = []
            if missing:
                reasons.append(f"Missing critical evidence: {', '.join(missing)}")
            if contradictions:
                reasons.append(f"Contradictions detected: {'; '.join(contradictions)}")
            if category == "unauthorized_fraud":
                reasons.append("Card-absent fraud claims require manual review of 3DS/device parameters before representment.")
            p1 += " | ".join(reasons)
            paragraphs.append(p1)
            structured_claims.append({
                "claim": "Case requires human analyst review due to missing critical proof or conflicting signals",
                "evidence_ids": [],
                "confidence": 0.85,
            })

        template_explanation = "\n\n".join(paragraphs)

        # -------------------------------------------------------------
        # 1b. OPTIONAL LLM DRAFT (only for cases we are actually defending)
        # -------------------------------------------------------------
        narrative_source = "template"
        draft_report: Dict[str, Any] = {"attempted": False, "accepted": False, "reason": "Not a contest case."}
        explanation = template_explanation

        if recommendation == "CONTEST":
            drafted, draft_report = self._draft_with_llm(nodes, dispute_data)
            if drafted:
                explanation = drafted
                narrative_source = "llm"
            elif draft_report.get("attempted"):
                narrative_source = "template_after_llm_rejected"

        # -------------------------------------------------------------
        # 2. ENTAILMENT & ANTI-HALLUCINATION CLAIM VERIFICATION
        # -------------------------------------------------------------
        grounded_count = 0
        total_count = len(structured_claims)
        hallucination_warnings: List[str] = []

        verified_claims_list = []
        for claim_obj in structured_claims:
            claim_text = claim_obj["claim"]
            ev_ids = claim_obj["evidence_ids"]
            is_grounded = True

            # If claim cites evidence IDs, verify every ID exists in the verified evidence nodes
            if ev_ids:
                for eid in ev_ids:
                    if eid not in nodes_by_id:
                        is_grounded = False
                        hallucination_warnings.append(f"Ungrounded Claim: '{claim_text}' references nonexistent node {eid}")
            else:
                if recommendation == "CONTEST":
                    is_grounded = False
                    hallucination_warnings.append(f"Ungrounded Claim without Citation: '{claim_text}'")

            if is_grounded:
                grounded_count += 1

            verified_claims_list.append({
                "claim": claim_text,
                "evidence_ids": ev_ids,
                "confidence": claim_obj["confidence"],
                "is_grounded": is_grounded,
            })

        grounded_rate = (grounded_count / total_count * 100.0) if total_count > 0 else 100.0

        # Razorpay Evidence Package Mapping
        evidence_package = []
        for node in nodes:
            if node["type"] in verification.get("available_evidence", []):
                evidence_package.append({
                    "evidence_id": node["evidence_id"],
                    "type": node["type"],
                    "razorpay_field": node["razorpay_field"],
                    "source": node["source"],
                    "summary": f"{node['type']} from {node['source']}",
                    "reliability": node["reliability"],
                })

        return {
            "explanation": explanation,
            "template_explanation": template_explanation,
            "narrative_source": narrative_source,
            "llm_draft": draft_report,
            "claims": verified_claims_list,
            "grounded_claims_rate": round(grounded_rate, 2),
            # The template claims are built from the same nodes they cite, so this
            # rate cannot fall below 100% by construction. Flagged as such so it is
            # not read as a hallucination measurement -- the real, falsifiable
            # check is llm_draft.verification.
            "claims_check_structurally_guaranteed": narrative_source != "llm",
            "unsupported_claims_count": len(hallucination_warnings),
            "hallucination_warnings": hallucination_warnings,
            "evidence_package": evidence_package,
        }
