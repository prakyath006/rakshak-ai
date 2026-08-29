"""LLM client (OpenRouter, OpenAI-compatible chat completions).

Rakshak keeps the *decision* deterministic on purpose -- a chargeback engine
that can be talked into contesting a merchant-fault case is worse than no engine
at all. The model is used only where free text has to be read or written:

  1. app/agents/extractor.py   reads unstructured evidence (claim text, support
                              email threads, policy prose) into structured signals
  2. app/agents/rebuttal.py    drafts the representment narrative

Both call sites verify the model's output against the evidence graph afterwards,
so a hallucination is caught rather than trusted.

Configuration (backend/.env):
    LLM_PROVIDER=openrouter        # 'none' disables all model calls
    LLM_MODEL=<openrouter model slug>
    OPENROUTER_API_KEY=sk-or-...
    LLM_BASE_URL=https://openrouter.ai/api/v1   # override for other OpenAI-compatible hosts

Run `python scripts/test_llm_key.py` to verify the key and list model slugs.
"""

from __future__ import annotations

import json
import re
import time
from typing import Any, Dict, Optional

import requests

from app.config import get_settings


class LLMError(RuntimeError):
    """Raised when a model call fails or returns unusable output."""


class LLMClient:
    """Minimal OpenAI-compatible chat client aimed at OpenRouter."""

    TIMEOUT = 60
    MAX_RETRIES = 3
    RETRY_BACKOFF = 2.0  # seconds; doubled per attempt

    def __init__(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        settings = get_settings()
        self.provider = (provider or getattr(settings, "llm_provider", "none") or "none").strip().lower()
        self.model = (model or getattr(settings, "llm_model", "") or "").strip()
        self.api_key = api_key if api_key is not None else getattr(settings, "openrouter_api_key", "")
        self.base_url = (base_url or getattr(settings, "llm_base_url", "https://openrouter.ai/api/v1")).rstrip("/")

    # ------------------------------------------------------------------
    # availability
    # ------------------------------------------------------------------
    @property
    def is_enabled(self) -> bool:
        return bool(self.provider != "none" and self.api_key and self.model)

    def disabled_reason(self) -> Optional[str]:
        """Why the model path is off, or None when it is on."""
        if self.provider == "none":
            return "LLM_PROVIDER is 'none' — deterministic template path in use."
        if not self.api_key:
            return "No API key set (OPENROUTER_API_KEY) — deterministic template path in use."
        if not self.model:
            return "No LLM_MODEL set — run scripts/test_llm_key.py to list available model slugs."
        return None

    def describe(self) -> Dict[str, Any]:
        """Status for /health and the UI badge."""
        return {
            "enabled": self.is_enabled,
            "provider": self.provider,
            "model": self.model or None,
            "base_url": self.base_url,
            "reason": self.disabled_reason() or f"Model calls active via {self.provider} ({self.model}).",
        }

    # ------------------------------------------------------------------
    # calls
    # ------------------------------------------------------------------
    def complete(
        self,
        system: str,
        user: str,
        max_tokens: int = 2000,
        temperature: float = 0.0,
        json_mode: bool = False,
    ) -> str:
        """Single-turn completion. Raises LLMError on any failure."""
        if not self.is_enabled:
            raise LLMError(self.disabled_reason() or "LLM client is not configured.")

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            # OpenRouter attribution headers; harmless on other hosts.
            "HTTP-Referer": "https://github.com/prakyath006/rakshak-ai",
            "X-Title": "Rakshak AI",
        }

        # Free-tier models rate-limit aggressively, so retry 429/5xx with backoff.
        # 402 (out of credits) and 401 (bad key) are not retried -- they will not
        # resolve on their own and retrying just delays a clear error message.
        resp = None
        last_error = ""
        for attempt in range(self.MAX_RETRIES + 1):
            try:
                resp = requests.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    data=json.dumps(payload),
                    timeout=self.TIMEOUT,
                )
            except requests.RequestException as exc:
                last_error = f"Could not reach {self.base_url}: {exc}"
                if attempt == self.MAX_RETRIES:
                    raise LLMError(last_error) from exc
                time.sleep(self.RETRY_BACKOFF * (2 ** attempt))
                continue

            if resp.status_code < 400:
                break

            last_error = f"{self.provider} returned {resp.status_code}: {resp.text[:400]}"
            if resp.status_code not in (429, 500, 502, 503, 504) or attempt == self.MAX_RETRIES:
                raise LLMError(last_error)
            time.sleep(self.RETRY_BACKOFF * (2 ** attempt))

        if resp is None or resp.status_code >= 400:
            raise LLMError(last_error or "Model call failed.")

        try:
            body = resp.json()
            return body["choices"][0]["message"]["content"] or ""
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise LLMError(f"Unexpected response shape from {self.provider}: {resp.text[:400]}") from exc

    def complete_json(
        self,
        system: str,
        user: str,
        max_tokens: int = 2000,
    ) -> Dict[str, Any]:
        """Completion parsed as a JSON object.

        Asks for JSON mode, then still parses defensively: not every model served
        through OpenRouter honours response_format, and several wrap the object
        in a markdown fence.
        """
        raw = self.complete(system, user, max_tokens=max_tokens, json_mode=True)
        parsed = _parse_json_object(raw)
        if parsed is None:
            raise LLMError(f"Model did not return a JSON object. Got: {raw[:300]}")
        return parsed


def _parse_json_object(raw: str) -> Optional[Dict[str, Any]]:
    """Best-effort extraction of a single JSON object from model output."""
    if not raw:
        return None

    text = raw.strip()

    # Strip a ```json ... ``` fence if present.
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()

    try:
        loaded = json.loads(text)
        return loaded if isinstance(loaded, dict) else None
    except json.JSONDecodeError:
        pass

    # Fall back to the outermost braces.
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        try:
            loaded = json.loads(text[start : end + 1])
            return loaded if isinstance(loaded, dict) else None
        except json.JSONDecodeError:
            return None
    return None


_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    """Process-wide client. Rebuilt only if settings are re-read."""
    global _client
    if _client is None:
        _client = LLMClient()
    return _client
