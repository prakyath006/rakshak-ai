"""Razorpay API Client & Dispute Integration Adapter.

Integrates with Razorpay's Disputes APIs:
- Fetch dispute details / list disputes
- Contest dispute (PATCH /v1/disputes/:id/contest with action=submit)
- Accept dispute (POST /v1/disputes/:id/accept)
- Webhook signature validation (HMAC SHA256)

MODE SEMANTICS
--------------
The adapter runs in exactly one of two modes, and it always says which:

  live       real HTTP calls to api.razorpay.com
  simulated  no network; deterministic stand-in responses

Every simulated response carries ``_simulated: true`` and ``_mode: "simulated"``.
Nothing here ever returns a synthetic payload that looks like a real one -- an
unlabelled success response is, by construction, a real one.
"""

import hmac
import hashlib
import json
import base64
from typing import Dict, Any, Optional

import requests

from app.config import get_settings


class RazorpayAPIError(RuntimeError):
    """Raised when a live Razorpay call fails. Carries the upstream detail."""

    def __init__(self, message: str, status_code: Optional[int] = None, body: str = ""):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class RazorpayAdapter:
    """Client for Razorpay Disputes API."""

    TIMEOUT = 15

    def __init__(
        self,
        key_id: Optional[str] = None,
        key_secret: Optional[str] = None,
        base_url: Optional[str] = None,
        mode: Optional[str] = None,
    ):
        settings = get_settings()
        self.key_id = key_id if key_id is not None else getattr(settings, "razorpay_key_id", "")
        self.key_secret = key_secret if key_secret is not None else getattr(settings, "razorpay_key_secret", "")
        self.base_url = base_url or getattr(settings, "razorpay_base_url", "https://api.razorpay.com/v1")
        self.webhook_secret = getattr(settings, "razorpay_webhook_secret", "rzp_webhook_secret_test")
        self.mode = self.resolve_mode(
            mode or getattr(settings, "razorpay_mode", "auto"),
            self.key_id,
            self.key_secret,
        )

    @staticmethod
    def resolve_mode(configured: str, key_id: str, key_secret: str) -> str:
        """Resolve 'auto' against the credentials actually present.

        An explicit live/simulated setting always wins, so a demo can be pinned
        to one mode regardless of what happens to be in the environment.
        """
        configured = (configured or "auto").strip().lower()
        if configured in ("live", "simulated"):
            return configured
        usable = (
            bool(key_id)
            and bool(key_secret)
            and key_id.startswith("rzp_")
            and not key_id.startswith("rzp_test_mock")
        )
        return "live" if usable else "simulated"

    @property
    def is_simulated(self) -> bool:
        return self.mode == "simulated"

    def describe(self) -> Dict[str, Any]:
        """Mode summary for /health and the UI mode badge."""
        if self.mode == "live":
            reason = "Razorpay credentials present; calls hit the live test API."
        elif self.key_id:
            reason = (
                "Simulated mode is pinned via RAZORPAY_MODE. Credentials are present but unused: "
                "responses are deterministic stand-ins and nothing leaves this process."
            )
        else:
            reason = (
                "No usable Razorpay credentials; responses are deterministic stand-ins "
                "and nothing leaves this process."
            )
        return {
            "mode": self.mode,
            "simulated": self.is_simulated,
            "key_id": self.key_id or None,
            "base_url": self.base_url,
            "reason": reason,
        }

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------
    def _get_auth_header(self) -> Dict[str, str]:
        auth_str = f"{self.key_id}:{self.key_secret}"
        encoded_auth = base64.b64encode(auth_str.encode("utf-8")).decode("utf-8")
        return {
            "Authorization": f"Basic {encoded_auth}",
            "Content-Type": "application/json",
        }

    def _request(self, method: str, path: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        try:
            resp = requests.request(
                method,
                url,
                headers=self._get_auth_header(),
                data=json.dumps(payload) if payload is not None else None,
                timeout=self.TIMEOUT,
            )
        except requests.RequestException as exc:
            raise RazorpayAPIError(f"Could not reach Razorpay ({method} {path}): {exc}") from exc

        if resp.status_code >= 400:
            raise RazorpayAPIError(
                f"Razorpay returned {resp.status_code} for {method} {path}",
                status_code=resp.status_code,
                body=resp.text[:500],
            )

        body = resp.json()
        body["_simulated"] = False
        body["_mode"] = "live"
        return body

    @staticmethod
    def _simulated(payload: Dict[str, Any]) -> Dict[str, Any]:
        payload["_simulated"] = True
        payload["_mode"] = "simulated"
        return payload

    # ------------------------------------------------------------------
    # webhooks
    # ------------------------------------------------------------------
    def verify_webhook_signature(self, raw_body: bytes, signature: str) -> bool:
        """Verify Razorpay webhook signature using HMAC SHA256."""
        if not signature:
            return False
        expected_sig = hmac.new(
            self.webhook_secret.encode("utf-8"),
            raw_body,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected_sig, signature)

    # ------------------------------------------------------------------
    # disputes
    # ------------------------------------------------------------------
    def list_disputes(self, count: int = 25) -> Dict[str, Any]:
        """List disputes on the account.

        Disputes are raised by the issuing bank / card network, so a merchant
        cannot create one through the API and a fresh test account returns an
        empty list. That is expected, not a failure.
        """
        if self.is_simulated:
            return self._simulated({"entity": "collection", "count": 0, "items": []})
        return self._request("GET", f"/disputes?count={count}")

    def fetch_dispute(self, dispute_id: str) -> Dict[str, Any]:
        """Fetch dispute entity details from Razorpay."""
        if self.is_simulated:
            return self._simulated({
                "id": dispute_id,
                "entity": "dispute",
                "payment_id": f"pay_{dispute_id[-6:]}",
                "amount": 4800000,
                "currency": "INR",
                "reason_code": "13.1",
                "status": "open",
                "phase": "chargeback",
                "respond_by": 1787652000,
                "evidence": {},
            })
        return self._request("GET", f"/disputes/{dispute_id}")

    def contest_dispute(
        self,
        dispute_id: str,
        evidence_payload: Dict[str, Any],
        summary: str,
        action: str = "submit",
    ) -> Dict[str, Any]:
        """Submit a representment package to contest a dispute.

        Maps structured evidence to Razorpay's contest entity fields:
        shipping_proof, billing_proof, customer_communication, proof_of_service,
        summary, and action (draft or submit).
        """
        payload = {
            "amount": evidence_payload.get("amount"),
            "summary": summary,
            "shipping_proof": evidence_payload.get("shipping_proof", []),
            "billing_proof": evidence_payload.get("billing_proof", []),
            "customer_communication": evidence_payload.get("customer_communication", []),
            "proof_of_service": evidence_payload.get("proof_of_service", []),
            "action": action,
        }

        if self.is_simulated:
            return self._simulated({
                "id": dispute_id,
                "entity": "dispute",
                "status": "under_review",
                "phase": "chargeback",
                "action": action,
                "summary": summary,
                "evidence": payload,
            })

        return self._request("PATCH", f"/disputes/{dispute_id}/contest", payload)

    def accept_dispute(self, dispute_id: str) -> Dict[str, Any]:
        """Accept a dispute without contesting (for merchant-fault cases)."""
        if self.is_simulated:
            return self._simulated({
                "id": dispute_id,
                "entity": "dispute",
                "status": "lost",
                "action": "accepted",
            })
        return self._request("POST", f"/disputes/{dispute_id}/accept")
