"""Application configuration."""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    database_url: str = "postgresql+asyncpg://rakshak:rakshak_dev@localhost:5432/rakshak"
    database_url_sync: str = "postgresql://rakshak:rakshak_dev@localhost:5432/rakshak"

    # Razorpay
    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""

    # LLM
    llm_provider: str = "openai"  # openai | gemini | ollama
    openai_api_key: str = ""
    gemini_api_key: str = ""

    # App
    app_name: str = "Rakshak AI"
    debug: bool = True

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache()
def get_settings() -> Settings:
    return Settings()
