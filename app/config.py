from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    base_url: str = "http://localhost:8000"
    database_url: str = "sqlite:///./reviewer.db"
    secret_key: str
    encryption_key: str
    admin_user: str = "admin"
    admin_password: str

    google_client_id: str = ""
    google_client_secret: str = ""
    gbp_mode: Literal["live", "fake"] = "fake"

    anthropic_api_key: str = ""
    claude_model: str = "claude-haiku-5-5"
    claude_effort: Literal["low", "medium", "high"] = "medium"

    resend_api_key: str = ""
    mail_from: str = ""
    mail_to: str = ""

    scheduler_enabled: bool = True
    poll_minutes: int = 15
    auto_post_enabled: bool = True
    auto_post_min_stars: int = 4
    backfill_per_hour: int = 6


@lru_cache
def get_settings() -> Settings:
    return Settings()
