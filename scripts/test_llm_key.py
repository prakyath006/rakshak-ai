"""Verify the OpenRouter key and list model slugs you can put in LLM_MODEL.

    python scripts/test_llm_key.py            # verify key + show a shortlist
    python scripts/test_llm_key.py --all      # dump every available slug
    python scripts/test_llm_key.py --free     # only models priced at 0
"""

import sys
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from app.config import get_settings  # noqa: E402
from app.services.llm import LLMClient, LLMError  # noqa: E402


def _price(model: dict) -> float:
    try:
        return float(model.get("pricing", {}).get("prompt", "0") or 0)
    except (TypeError, ValueError):
        return 0.0


def main() -> int:
    settings = get_settings()
    client = LLMClient()

    print("=" * 68)
    print("OPENROUTER / LLM CONFIGURATION CHECK")
    print("=" * 68)
    print(f"  provider : {client.provider}")
    print(f"  base_url : {client.base_url}")
    print(f"  model    : {client.model or '(not set)'}")
    print(f"  api_key  : {'set (' + client.api_key[:12] + '...)' if client.api_key else '(not set)'}")
    print()

    if not client.api_key:
        print("[FAIL] No OPENROUTER_API_KEY in backend/.env.")
        print("       Get one at https://openrouter.ai/keys, then add:")
        print("         LLM_PROVIDER=openrouter")
        print("         OPENROUTER_API_KEY=sk-or-...")
        print("         LLM_MODEL=<slug from the list this script prints>")
        return 1

    # ---- list models -------------------------------------------------
    show_all = "--all" in sys.argv
    free_only = "--free" in sys.argv

    print("[TEST 1] GET /models")
    try:
        resp = requests.get(
            f"{client.base_url}/models",
            headers={"Authorization": f"Bearer {client.api_key}"},
            timeout=20,
        )
    except requests.RequestException as exc:
        print(f"  [FAIL] {exc}")
        return 1

    print(f"  Status: {resp.status_code}")
    if resp.status_code == 401:
        print("  [FAIL] Key rejected. Check OPENROUTER_API_KEY.")
        return 1
    if resp.status_code >= 400:
        print(f"  [FAIL] {resp.text[:300]}")
        return 1

    models = resp.json().get("data", [])
    print(f"  [PASS] {len(models)} models available")
    print()

    shown = models if (show_all or free_only) else models[:0]
    if free_only:
        shown = [m for m in models if _price(m) == 0.0]

    if shown:
        print(f"  {'SLUG':<52} {'CTX':>9}  $/1M in")
        print(f"  {'-' * 52} {'-' * 9}  -------")
        for m in sorted(shown, key=lambda x: x.get("id", "")):
            ctx = m.get("context_length") or 0
            print(f"  {m.get('id', ''):<52} {ctx:>9}  {_price(m) * 1_000_000:.2f}")
        print()
    elif not client.model:
        print("  Re-run with --all to list every slug, or --free for zero-cost models.")
        print()

    # ---- live completion --------------------------------------------
    if not client.model:
        print("[SKIP] TEST 2: set LLM_MODEL in backend/.env to test a completion.")
        return 0

    valid = {m.get("id") for m in models}
    if client.model not in valid:
        print(f"[WARN] LLM_MODEL '{client.model}' is not in the available list.")

    print(f"[TEST 2] POST /chat/completions  (model={client.model})")
    try:
        out = client.complete_json(
            system='Reply with JSON only.',
            user='Return exactly {"ok": true, "engine": "rakshak"} and nothing else.',
            max_tokens=100,
        )
        print(f"  [PASS] Parsed JSON response: {out}")
    except LLMError as exc:
        print(f"  [FAIL] {exc}")
        return 1

    print()
    print("=" * 68)
    print("RESULT: LLM path is configured and reachable.")
    print("=" * 68)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
