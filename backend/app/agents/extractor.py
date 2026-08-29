"""Stage 3.5: Unstructured Evidence Extraction (LLM, quote-grounded).

WHY THIS EXISTS
---------------
Every deterministic rule in verifier.py reads *structured* fields. The only way
it touches free text is a handful of substring tests -- `"lost" in msg_lower`,
`"will refund" in msg_lower`. That works on templated data and fails on anything
a real support inbox contains: "the courier says it never made it off the van",
"we'll get that money back to you this week", "arrived but the box was empty".

This stage reads that text properly. It is the one place a model is allowed to
interpret rather than match.

THE SAFETY CONTRACT
-------------------
Two invariants keep a hallucinating model from ever costing the merchant a case:

  1. QUOTE GROUNDING. Every signal must cite a verbatim span of the source
     message. We re-check that span against the original text and discard any
     signal whose quote is not actually there. This check can and does fail --
     unlike the claim verifier in rebuttal.py, which cites IDs it just read out
     of the same dict it is checking against.

  2. MONOTONE TOWARD CAUTION. Surviving signals may only ever move a decision
     from CONTEST toward REVIEW. They can never create or strengthen a contest.
     So the worst a confidently-wrong model can do is send a winnable case to a
     human -- it can never cause a false contest against merchant fault.

With LLM_PROVIDER=none the stage is inert and the pipeline behaves exactly as it
did before, which is what keeps the benchmark suites reproducible.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from app.services.llm import LLMClient, LLMError, get_llm_client

# Signals the model is allowed to emit. Anything else is dropped.
SIGNAL_VOCABULARY = {
    "ACKNOWLEDGES_RECEIPT",            # customer confirms they got the goods
    "DENIES_RECEIPT",                  # customer says they did not
    "MERCHANT_ADMITS_LOSS",            # merchant concedes the shipment was lost/undelivered
    "MERCHANT_PROMISED_REFUND",        # merchant committed to a FUTURE refund
    "MERCHANT_CONFIRMS_REFUND_DONE",   # merchant states a refund was ALREADY issued
    "REPORTS_ITEM_MISMATCH",           # wrong/damaged/not-as-described item
    "REQUESTS_CANCELLATION",           # customer asked to cancel
    "NEUTRAL",                         # nothing decision-relevant
}

# Signals that indicate the merchant's own words undercut a contest.
MERCHANT_FAULT_SIGNALS = {
    "MERCHANT_ADMITS_LOSS",
    "MERCHANT_PROMISED_REFUND",
}

# Signals that contradict a "customer received it" defence.
CONTEST_UNDERMINING_SIGNALS = MERCHANT_FAULT_SIGNALS | {
    "DENIES_RECEIPT",
    "REPORTS_ITEM_MISMATCH",
    "REQUESTS_CANCELLATION",
}

SYSTEM_PROMPT = """You are an evidence-reading assistant for a payment dispute (chargeback) system.

You are given the free-text messages exchanged between a merchant and a customer about one disputed order. Your ONLY job is to label what each message actually says. You do NOT decide whether the merchant should contest the dispute.

For each message, emit zero or more signals. Allowed signal values, exactly:
- ACKNOWLEDGES_RECEIPT: the customer states they received the goods
- DENIES_RECEIPT: the customer states they did not receive the goods
- MERCHANT_ADMITS_LOSS: the merchant concedes the shipment was lost, undelivered, or never dispatched
- MERCHANT_PROMISED_REFUND: the merchant says a refund WILL be issued (future tense: "we will process your refund", "your refund will be credited within 48 hours")
- MERCHANT_CONFIRMS_REFUND_DONE: the merchant says a refund HAS BEEN issued (past tense: "your refund has been processed", "we refunded INR 12,000 on 11-Aug")
- REPORTS_ITEM_MISMATCH: the item is reported wrong, damaged, incomplete, or not as described
- REQUESTS_CANCELLATION: the customer asks to cancel the order
- NEUTRAL: nothing decision-relevant

HARD RULES:
1. "quote" MUST be copied character-for-character from that message's text. Do not paraphrase, reword, fix spelling, translate, or trim mid-word. If you cannot copy an exact span that supports the signal, do not emit the signal.
2. Judge only what the text states. Do not infer from the order status, timestamps, or what would be convenient.
3. Hedged or conditional language ("we may be able to refund", "it might have been lost") is NOT a commitment or an admission. Use NEUTRAL and say so in "reasoning".
4. If a message is genuinely ambiguous, use NEUTRAL with a low confidence. But a clear, plainly-worded statement should get its specific label — do not retreat to NEUTRAL just because a message is short or the wording is ordinary.

Return ONLY a JSON object of this exact shape:
{
  "signals": [
    {
      "communication_id": "<the id given for that message>",
      "signal": "<one allowed value>",
      "quote": "<verbatim span copied from that message>",
      "confidence": <number between 0 and 1>,
      "reasoning": "<one short sentence>"
    }
  ],
  "claim_summary": "<one sentence describing what the cardholder is alleging>"
}"""


def _normalize(text: str) -> str:
    """Collapse whitespace and case so a quote match is not defeated by spacing."""
    return re.sub(r"\s+", " ", (text or "")).strip().lower()


class EvidenceExtractor:
    """Reads unstructured dispute text into verified, structured signals."""

    def __init__(self, client: Optional[LLMClient] = None):
        self.client = client or get_llm_client()

    # ------------------------------------------------------------------
    def extract(self, dispute_data: Dict[str, Any]) -> Dict[str, Any]:
        """Return the extraction report. Never raises -- a model failure degrades
        to the deterministic path and is reported in 'reason'."""
        comms = dispute_data.get("communications", []) or []
        claim_text = dispute_data.get("dispute", {}).get("customer_claim_text", "")

        base: Dict[str, Any] = {
            "enabled": False,
            "model": self.client.model or None,
            "reason": None,
            "signals": [],
            "rejected_signals": [],
            # Keep this shape identical to the one built after a successful run --
            # every early return (LLM off, no text, model error) uses it, and a
            # consumer must not have to branch on which path produced it.
            "quote_verification": {
                "proposed": 0,
                "verbatim": 0,
                "rejected": 0,
                "neutral": 0,
                "grounding_rate": None,
            },
            "advisory_flags": [],
            "claim_summary": None,
        }

        if not self.client.is_enabled:
            base["reason"] = self.client.disabled_reason()
            return base

        if not comms and not claim_text:
            base["enabled"] = True
            base["reason"] = "No unstructured text on this dispute; nothing to extract."
            return base

        try:
            raw = self.client.complete_json(
                system=SYSTEM_PROMPT,
                user=self._build_user_prompt(dispute_data, comms, claim_text),
                max_tokens=1500,
            )
        except LLMError as exc:
            base["reason"] = f"Model call failed ({exc}). Deterministic path used."
            return base

        base["enabled"] = True
        base["claim_summary"] = raw.get("claim_summary")

        verified, rejected, neutral = self._verify_quotes(raw.get("signals", []), comms)
        proposed = len(verified) + len(rejected)

        base["signals"] = verified
        base["rejected_signals"] = rejected
        base["quote_verification"] = {
            "proposed": proposed,
            "verbatim": len(verified),
            "rejected": len(rejected),
            # Counted separately: NEUTRAL carries no decision weight and no quote to
            # check, but a run that is all-NEUTRAL means the model read the mail and
            # found nothing -- which is different from it not having run at all.
            "neutral": neutral,
            # None rather than a flattering 100% when there was nothing to check.
            "grounding_rate": round(len(verified) / proposed * 100, 2) if proposed else None,
        }
        base["advisory_flags"] = self._derive_flags(verified, dispute_data)
        return base

    # ------------------------------------------------------------------
    def _build_user_prompt(
        self,
        dispute_data: Dict[str, Any],
        comms: List[Dict[str, Any]],
        claim_text: str,
    ) -> str:
        order_id = dispute_data.get("order", {}).get("order_id", "unknown")
        lines = [
            f"Disputed order: {order_id}",
            f"Cardholder's stated claim: {claim_text or '(none provided)'}",
            "",
            "Messages:",
        ]
        for idx, comm in enumerate(comms, start=1):
            cid = comm.get("communication_id") or f"COMM-{idx}"
            direction = comm.get("direction", "unknown")
            speaker = "merchant" if direction == "outbound" else "customer"
            lines.append(
                f"\n[{cid}] from={speaker} channel={comm.get('channel', 'email')} "
                f"sent={comm.get('timestamp', 'unknown')}\n"
                f"subject: {comm.get('subject', '(no subject)')}\n"
                f"body: {comm.get('message', '')}"
            )
        return "\n".join(lines)

    # ------------------------------------------------------------------
    def _verify_quotes(
        self,
        proposed: Any,
        comms: List[Dict[str, Any]],
    ) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]], int]:
        """Keep only signals whose quote genuinely appears in the cited message.

        Returns (verified, rejected, neutral_count).
        """
        by_id = {
            (c.get("communication_id") or f"COMM-{i}"): c
            for i, c in enumerate(comms, start=1)
        }

        verified: List[Dict[str, Any]] = []
        rejected: List[Dict[str, Any]] = []
        neutral = 0

        if not isinstance(proposed, list):
            return verified, rejected, neutral

        for item in proposed:
            if not isinstance(item, dict):
                continue

            cid = item.get("communication_id")
            signal = item.get("signal")
            quote = item.get("quote") or ""

            if signal not in SIGNAL_VOCABULARY:
                rejected.append({**item, "rejection": f"Signal '{signal}' is not in the allowed vocabulary."})
                continue

            if signal == "NEUTRAL":
                neutral += 1
                continue  # carries no decision weight and no quote to verify

            source = by_id.get(cid)
            if source is None:
                rejected.append({**item, "rejection": f"Cites communication '{cid}', which does not exist on this dispute."})
                continue

            if not _normalize(quote):
                rejected.append({**item, "rejection": "Signal carries no quote."})
                continue

            if _normalize(quote) not in _normalize(source.get("message", "")):
                rejected.append({**item, "rejection": "Quote is not a verbatim span of the cited message."})
                continue

            verified.append({
                "communication_id": cid,
                "signal": signal,
                "quote": quote,
                "confidence": item.get("confidence"),
                "reasoning": item.get("reasoning"),
                "direction": source.get("direction"),
                "verified": True,
            })

        return verified, rejected, neutral

    # ------------------------------------------------------------------
    def _derive_flags(
        self,
        signals: List[Dict[str, Any]],
        dispute_data: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Turn verified signals into advisory flags.

        Every flag here is a reason to be *more* cautious. There is deliberately
        no flag that supports contesting -- see the safety contract above.
        """
        flags: List[Dict[str, Any]] = []
        target_order = dispute_data.get("order", {}).get("order_id")
        comms_by_id = {
            c.get("communication_id"): c for c in dispute_data.get("communications", []) or []
        }

        for sig in signals:
            name = sig["signal"]
            if name not in CONTEST_UNDERMINING_SIGNALS:
                continue

            # Deterministic backstop: a refund "promise" that the ledger shows was
            # actually paid is not merchant fault -- it is the merchant's defence.
            # The model has to read tense correctly to get MERCHANT_PROMISED_REFUND
            # vs MERCHANT_CONFIRMS_REFUND_DONE right; this check means it does not
            # have to. Without it, a tense misread silently costs a winnable case.
            if name == "MERCHANT_PROMISED_REFUND" and _refund_settled(dispute_data):
                flags.append({
                    "flag": "REFUND_PROMISE_ALREADY_SETTLED",
                    "severity": "info",
                    "signal": name,
                    "communication_id": sig["communication_id"],
                    "quote": sig["quote"],
                    "detail": (
                        "Correspondence reads as a refund commitment, but the refund ledger "
                        "shows a processed refund covering the disputed amount. Treated as "
                        "supporting evidence, not merchant fault."
                    ),
                })
                continue

            source = comms_by_id.get(sig["communication_id"], {})
            source_order = source.get("order_id")

            # A signal lifted from another order's correspondence proves nothing
            # about this dispute -- but the fact that it is in the file at all is
            # worth telling the analyst.
            if source_order and target_order and source_order != target_order:
                flags.append({
                    "flag": "CROSS_ORDER_SIGNAL",
                    "severity": "info",
                    "signal": name,
                    "communication_id": sig["communication_id"],
                    "quote": sig["quote"],
                    "detail": (
                        f"Message belongs to order {source_order}, not the disputed order "
                        f"{target_order}. Excluded from the merchant-fault assessment."
                    ),
                })
                continue

            if name in MERCHANT_FAULT_SIGNALS:
                flags.append({
                    "flag": "MERCHANT_FAULT_IN_CORRESPONDENCE",
                    "severity": "blocking",
                    "signal": name,
                    "communication_id": sig["communication_id"],
                    "quote": sig["quote"],
                    "detail": (
                        "The merchant's own written words undercut a representment. "
                        "Contest is downgraded to human review."
                    ),
                })
            else:
                flags.append({
                    "flag": "CUSTOMER_CONTRADICTS_DEFENCE",
                    "severity": "caution",
                    "signal": name,
                    "communication_id": sig["communication_id"],
                    "quote": sig["quote"],
                    "detail": "Customer correspondence conflicts with the evidence-based defence.",
                })

        return flags


def _refund_settled(dispute_data: Dict[str, Any]) -> bool:
    """True when a processed refund covers (most of) the disputed amount."""
    disputed = float(dispute_data.get("dispute", {}).get("amount", 0) or 0)
    processed = sum(
        float(r.get("amount", 0) or 0)
        for r in (dispute_data.get("refunds") or [])
        if r.get("status") == "processed"
    )
    if processed <= 0:
        return False
    if disputed <= 0:
        return True
    return processed >= disputed * 0.95


def blocking_flags(extraction: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Flags severe enough to force a CONTEST down to REVIEW."""
    return [f for f in extraction.get("advisory_flags", []) if f.get("severity") == "blocking"]
