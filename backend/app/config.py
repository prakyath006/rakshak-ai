"""Application configuration with graceful environment fallback."""

import os
from functools import lru_cache

try:
    from pydantic_settings import BaseSettings

    class Settings(BaseSettings):
        database_url: str = "postgresql+asyncpg://rakshak:rakshak_dev@localhost:5432/rakshak"
        database_url_sync: str = "postgresql://rakshak:rakshak_dev@localhost:5432/rakshak"
        razorpay_key_id: str = ""
        razorpay_key_secret: str = ""
        razorpay_base_url: str = "https://api.razorpay.com/v1"
        razorpay_webhook_secret: str = "rzp_webhook_secret_test"
        llm_provider: str = "openai"
        openai_api_key: str = ""
        gemini_api_key: str = ""
        app_name: str = "Rakshak AI"
        debug: bool = True

        model_config = {"env_file": ".env", "extra": "ignore"}

except ImportError:
    class Settings:
        def __init__(self):
            self.database_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://rakshak:rakshak_dev@localhost:5432/rakshak")
            self.database_url_sync = os.getenv("DATABASE_URL_SYNC", "postgresql://rakshak:rakshak_dev@localhost:5432/rakshak")
            self.razorpay_key_id = os.getenv("RAZORPAY_KEY_ID", "")
            self.razorpay_key_secret = os.getenv("RAZORPAY_KEY_SECRET", "")
            self.razorpay_base_url = os.getenv("RAZORPAY_BASE_URL", "https://api.razorpay.com/v1")
            self.razorpay_webhook_secret = os.getenv("RAZORPAY_WEBHOOK_SECRET", "rzp_webhook_secret_test")
            self.llm_provider = os.getenv("LLM_PROVIDER", "openai")
            self.openai_api_key = os.getenv("OPENAI_API_KEY", "")
            self.gemini_api_key = os.getenv("GEMINI_API_KEY", "")
            self.app_name = "Rakshak AI"
            self.debug = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()
