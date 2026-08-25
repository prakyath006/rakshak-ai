"""FastAPI Application with Idempotency, Safety Gates, Policy Versioning, and Razorpay Integration."""

import json
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, Body, Header, Request, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.config import get_settings
from app.agents.pipeline import DisputePipeline
from app.services.razorpay_adapter import RazorpayAdapter

app = FastAPI(
    title="Rakshak AI — Chargeback Evidence & Representment Agent",
    description="Backend API for Rakshak AI (Razorpay AI Buildathon Track 02)",
    version="2.3.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

pipeline = DisputePipeline()
razorpay_client = RazorpayAdapter()

# Core In-Memory Stores (with Idempotency Keys)
DATA_PATH = Path(__file__).parent.parent.parent / "data" / "golden_cases.json"
CASE_STORE: Dict[str, Dict[str, Any]] = {}
DECISION_CACHE: Dict[str, Dict[str, Any]] = {}
SUBMISSION_STORE: Dict[str, Dict[str, Any]] = {}
PROCESSED_WEBHOOK_EVENTS: set = set()
SUBMISSION_IDEMPOTENCY_KEYS: Dict[str, str] = {}

ENGINE_VERSION = "rakshak-decision-v2.3"
POLICY_VERSION = "evidence-policy-v1.4"
MAPPING_VERSION = "rzp-dispute-map-v1.2"


def load_initial_cases():
    global CASE_STORE
    if DATA_PATH.exists():
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            cases = json.load(f)
            for c in cases:
                cid = c.get("case_id") or c.get("dispute", {}).get("dispute_id")
                CASE_STORE[cid] = c


load_initial_cases()


class ApprovalRequest(BaseModel):
    action: str  # 'CONTEST', 'ACCEPT', 'ESCALATE'
    reviewer_notes: Optional[str] = None
    custom_rebuttal: Optional[str] = None
    idempotency_key: Optional[str] = None


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "app": "Rakshak AI",
        "engine_version": ENGINE_VERSION,
        "policy_version": POLICY_VERSION,
        "mapping_version": MAPPING_VERSION,
        "razorpay_mode": "test_api_adapter",
    }


@app.get("/api/disputes")
def list_disputes():
    """List all disputes sorted by urgency deadline."""
    summaries = []
    for cid, c in CASE_STORE.items():
        disp = c.get("dispute", {})
        summaries.append({
            "case_id": c.get("case_id", cid),
            "dispute_id": disp.get("dispute_id", cid),
            "title": c.get("title", f"Dispute {cid}"),
            "category": c.get("category"),
            "reason_code": c.get("reason_code"),
            "reason_description": c.get("reason_description"),
            "amount": disp.get("amount"),
            "currency": "INR",
            "phase": disp.get("phase", "chargeback"),
            "status": disp.get("status", "open"),
            "respond_by": disp.get("respond_by", "2026-08-30T18:30:00Z"),
            "customer_name": c.get("customer", {}).get("name"),
            "expected_decision": c.get("expected_decision"),
            "submission_status": SUBMISSION_STORE.get(cid, {}).get("status", "PENDING_REVIEW"),
        })
    # Sort by respond_by timestamp (most urgent first)
    summaries.sort(key=lambda x: str(x.get("respond_by", "")))
    return {"disputes": summaries, "total": len(summaries)}


@app.get("/api/disputes/{case_or_dispute_id}")
def get_dispute(case_or_dispute_id: str):
    """Retrieve full details of a dispute."""
    for cid, c in CASE_STORE.items():
        if cid == case_or_dispute_id or c.get("dispute", {}).get("dispute_id") == case_or_dispute_id:
            return c
    raise HTTPException(status_code=404, detail="Dispute not found")


@app.post("/api/disputes/{case_or_dispute_id}/investigate")
def investigate_dispute(case_or_dispute_id: str):
    """Execute Rakshak's 6-stage autonomous investigation and evidence verification."""
    case_data = None
    for cid, c in CASE_STORE.items():
        if cid == case_or_dispute_id or c.get("dispute", {}).get("dispute_id") == case_or_dispute_id:
            case_data = c
            break

    if not case_data:
        raise HTTPException(status_code=404, detail="Dispute not found")

    result = pipeline.run(case_data)
    
    # Attach audit provenance and reproducibility versioning
    raw_hash = hashlib.sha256(json.dumps(case_data, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:16]
    result["versioning"] = {
        "engine_version": ENGINE_VERSION,
        "policy_version": POLICY_VERSION,
        "mapping_version": MAPPING_VERSION,
        "reproducibility_hash": raw_hash,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    DECISION_CACHE[case_or_dispute_id] = result
    return result


@app.post("/api/disputes/{case_or_dispute_id}/approve-and-submit")
def approve_and_submit(case_or_dispute_id: str, request: ApprovalRequest):
    """Human Approval Gate with Safety Enforcements and Submission Idempotency."""
    case_data = None
    target_id = case_or_dispute_id
    for cid, c in CASE_STORE.items():
        if cid == case_or_dispute_id or c.get("dispute", {}).get("dispute_id") == case_or_dispute_id:
            case_data = c
            target_id = c.get("dispute", {}).get("dispute_id", cid)
            break

    if not case_data:
        raise HTTPException(status_code=404, detail="Dispute not found")

    # Idempotency Check: Prevent duplicate submissions on double-clicks or retries
    idem_key = request.idempotency_key or f"idem_{case_or_dispute_id}_{request.action}"
    if case_or_dispute_id in SUBMISSION_STORE:
        existing_sub = SUBMISSION_STORE[case_or_dispute_id]
        if existing_sub.get("status") in ["CONTESTED_SUBMITTED", "DISPUTE_ACCEPTED"]:
            return {
                "status": "idempotent_replay",
                "action": existing_sub.get("status"),
                "message": "Dispute already submitted. Returning existing submission record.",
                "submission": existing_sub,
            }

    # Fetch investigation decision
    inv_result = DECISION_CACHE.get(case_or_dispute_id) or pipeline.run(case_data)
    rec = inv_result["decision"]["recommendation"]

    # -------------------------------------------------------------
    # SAFETY GATE: Block Contests on Merchant Fault Cases
    # -------------------------------------------------------------
    if request.action == "CONTEST" and rec == "DO_NOT_CONTEST":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="SAFETY VIOLATION: Rakshak policy engine identified merchant fault. Automatic/Human representment is strictly blocked.",
        )

    if request.action == "CONTEST":
        rebuttal = inv_result.get("rebuttal", {})
        summary_text = request.custom_rebuttal or rebuttal.get("explanation", "")
        
        evidence_payload = {
            "amount": case_data.get("dispute", {}).get("amount"),
            "shipping_proof": [e["evidence_id"] for e in rebuttal.get("evidence_package", []) if e.get("razorpay_field") == "shipping_proof"],
            "billing_proof": [e["evidence_id"] for e in rebuttal.get("evidence_package", []) if e.get("razorpay_field") == "billing_proof"],
            "customer_communication": [e["evidence_id"] for e in rebuttal.get("evidence_package", []) if e.get("razorpay_field") == "customer_communication"],
            "proof_of_service": [e["evidence_id"] for e in rebuttal.get("evidence_package", []) if e.get("razorpay_field") == "proof_of_service"],
        }

        # Submit via Razorpay API adapter
        rzp_resp = razorpay_client.contest_dispute(
            dispute_id=target_id,
            evidence_payload=evidence_payload,
            summary=summary_text,
            action="submit",
        )

        sub_record = {
            "status": "CONTESTED_SUBMITTED",
            "submitted_at": datetime.now(timezone.utc).isoformat(),
            "razorpay_response": rzp_resp,
            "reviewer_notes": request.reviewer_notes,
            "idempotency_key": idem_key,
            "engine_version": ENGINE_VERSION,
        }
        SUBMISSION_STORE[case_or_dispute_id] = sub_record
        SUBMISSION_IDEMPOTENCY_KEYS[idem_key] = target_id

        return {
            "status": "success",
            "action": "CONTESTED_SUBMITTED",
            "message": f"Representment package successfully submitted to Razorpay API for dispute {target_id}",
            "razorpay_dispute": rzp_resp,
        }

    elif request.action == "ACCEPT":
        rzp_resp = razorpay_client.accept_dispute(dispute_id=target_id)
        sub_record = {
            "status": "DISPUTE_ACCEPTED",
            "accepted_at": datetime.now(timezone.utc).isoformat(),
            "razorpay_response": rzp_resp,
            "idempotency_key": idem_key,
        }
        SUBMISSION_STORE[case_or_dispute_id] = sub_record
        return {
            "status": "success",
            "action": "DISPUTE_ACCEPTED",
            "message": f"Dispute {target_id} safely accepted via Razorpay API (no contest submitted).",
            "razorpay_dispute": rzp_resp,
        }

    else:  # ESCALATE
        sub_record = {
            "status": "ESCALATED_MANUAL_REVIEW",
            "escalated_at": datetime.now(timezone.utc).isoformat(),
            "reviewer_notes": request.reviewer_notes,
        }
        SUBMISSION_STORE[case_or_dispute_id] = sub_record
        return {
            "status": "success",
            "action": "ESCALATED_MANUAL_REVIEW",
            "message": f"Dispute {target_id} escalated for deeper manual merchant investigation.",
        }


@app.post("/api/webhooks/razorpay")
async def razorpay_webhook(
    request: Request,
    x_razorpay_signature: Optional[str] = Header(None),
):
    """Ingest Razorpay dispute webhooks with HMAC Verification & Event Idempotency."""
    raw_body = await request.body()
    
    # Webhook signature security check
    if x_razorpay_signature:
        is_valid = razorpay_client.verify_webhook_signature(raw_body, x_razorpay_signature)
        if not is_valid:
            raise HTTPException(status_code=400, detail="Invalid Razorpay webhook signature")

    payload = json.loads(raw_body.decode("utf-8"))
    event_id = payload.get("id") or payload.get("event_id") or hashlib.sha256(raw_body).hexdigest()[:16]
    event = payload.get("event", "")

    # Idempotency Check: Don't re-process duplicate webhook events
    if event_id in PROCESSED_WEBHOOK_EVENTS:
        return {
            "status": "idempotent_duplicate_ignored",
            "event_id": event_id,
            "event": event,
            "processed": False,
        }

    dispute_entity = payload.get("payload", {}).get("dispute", {}).get("entity", {})
    disp_id = dispute_entity.get("id")

    if event in ["payment.dispute.created", "payment.dispute.action_required"] and disp_id:
        new_case = {
            "case_id": f"RZP-{disp_id[-6:]}",
            "title": f"Incoming Dispute {disp_id}",
            "category": "goods_not_received" if dispute_entity.get("reason_code") == "13.1" else "general_dispute",
            "reason_code": dispute_entity.get("reason_code", "13.1"),
            "reason_description": "Dispute created via webhook",
            "merchant": {"merchant_id": "MERCH-001", "name": "Apex Electronics"},
            "customer": {"customer_id": "CUS-WEBHOOK", "name": "Customer", "email": "customer@example.com"},
            "product": {"product_id": "PROD-WEBHOOK", "name": "Purchased Item", "price": dispute_entity.get("amount", 0)/100.0},
            "order": {"order_id": f"ORD-{disp_id[-6:]}", "quantity": 1, "order_amount": dispute_entity.get("amount", 0)/100.0, "order_status": "delivered", "created_at": "2026-08-20T10:00:00Z"},
            "payment": {"payment_id": dispute_entity.get("payment_id", "pay_000"), "amount": dispute_entity.get("amount", 0)/100.0, "payment_method": "card", "card_network": "visa", "payment_timestamp": "2026-08-20T10:05:00Z"},
            "shipment": {"shipment_id": f"SHIP-{disp_id[-6:]}", "carrier": "BlueDart", "tracking_number": "BD-998811", "shipped_at": "2026-08-21T12:00:00Z", "delivered_at": "2026-08-23T16:00:00Z", "delivery_status": "delivered", "delivery_address_match": True, "items_shipped": 1},
            "dispute": dispute_entity,
        }
        CASE_STORE[disp_id] = new_case
        CASE_STORE[new_case["case_id"]] = new_case
        PROCESSED_WEBHOOK_EVENTS.add(event_id)

    return {
        "status": "received",
        "event_id": event_id,
        "event": event,
        "dispute_id": disp_id,
        "processed": True,
    }
