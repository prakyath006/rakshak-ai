"""Application configuration.

Loads environment from the nearest .env files BEFORE settings are constructed, so
configuration behaves identically whether or not `pydantic-settings` is installed.
"""

import os
from functools import lru_cache
from pathlib import Path

# ---------------------------------------------------------------------------
# Explicit .env loading.
# Previously nothing called load_dotenv(), so backend/.env was only ever read
# inside Docker (where compose injected the vars). Locally every credential
# resolved to "" and the Razorpay adapter silently fell back to simulated mode.
# ---------------------------------------------------------------------------
_BACKEND_DIR = Path(__file__).resolve().parent.parent   # backend/
_REPO_ROOT = _BACKEND_DIR.parent                        # repo root

try:
    from dotenv import load_dotenv

    for _env_path in (_BACKEND_DIR / ".env", _REPO_ROOT / ".env"):
        if _env_path.exists():
            load_dotenv(_env_path, override=False)
except ImportError:  # python-dotenv absent; rely on the ambient environment
    pass


def _env(key: str, default: str = "") -> str:
    return os.getenv(key, default)


try:
    from pydantic_settings import BaseSettings

    class Settings(BaseSettings):
        razorpay_key_id: str = ""
        razorpay_key_secret: str = ""
        razorpay_base_url: str = "https://api.razorpay.com/v1"
        razorpay_webhook_secret: str = "rzp_webhook_secret_test"
        # auto | simulated | live -- see RazorpayAdapter.resolve_mode()
        razorpay_mode: str = "auto"
        # LLM: 'none' disables every model call and keeps the deterministic path.
        llm_provider: str = "none"
        llm_model: str = ""
        llm_base_url: str = "https://openrouter.ai/api/v1"
        openrouter_api_key: str = ""
        app_name: str = "Rakshak AI"
        debug: bool = True

        model_config = {"env_file": str(_BACKEND_DIR / ".env"), "extra": "ignore"}

except ImportError:
    class Settings:
        def __init__(self):
            self.razorpay_key_id = _env("RAZORPAY_KEY_ID")
            self.razorpay_key_secret = _env("RAZORPAY_KEY_SECRET")
            self.razorpay_base_url = _env("RAZORPAY_BASE_URL", "https://api.razorpay.com/v1")
            self.razorpay_webhook_secret = _env("RAZORPAY_WEBHOOK_SECRET", "rzp_webhook_secret_test")
            self.razorpay_mode = _env("RAZORPAY_MODE", "auto")
            self.llm_provider = _env("LLM_PROVIDER", "none")
            self.llm_model = _env("LLM_MODEL", "")
            self.llm_base_url = _env("LLM_BASE_URL", "https://openrouter.ai/api/v1")
            self.openrouter_api_key = _env("OPENROUTER_API_KEY")
            self.app_name = "Rakshak AI"
            self.debug = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()
