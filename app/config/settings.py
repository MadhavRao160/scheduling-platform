from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

    # --- Part 1 ---
    database_url: str
    environment: Literal["development", "production"] = "development"
    port: int = 8000

    # --- Slots ---
    slot_generation_days: int = Field(default=30, gt=0)

    # --- Temporal ---
    temporal_address: str = "localhost:7233"
    temporal_namespace: str = "default"
    temporal_task_queue: str = "calendly-tasks"
    temporal_enabled: bool = True

    # --- Email ---
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_user: str = ""
    smtp_pass: SecretStr = SecretStr("")
    email_from: str = "Scheduler <noreply@example.com>"

    # --- Google ---
    google_client_id: str = ""
    google_client_secret: SecretStr = SecretStr("")
    google_redirect_uri: str = ""
    google_refresh_token: SecretStr = SecretStr("")
    google_calendar_id: str = "primary"
    google_sender_email: str = "info@example.com"

    @field_validator("google_refresh_token", mode="before")
    @classmethod
    def _clean_refresh_token(cls, value: object) -> object:
        """Remove stray spaces and quotes from a pasted token."""
        if isinstance(value, str):
            return value.strip().strip("\"'").strip()
        return value

    @property
    def is_development(self) -> bool:
        return self.environment == "development"

    @property
    def google_enabled(self) -> bool:
        """True only when everything needed to call Google is present."""
        return bool(
            self.google_client_id
            and self.google_client_secret.get_secret_value()
            and self.google_refresh_token.get_secret_value()
        )


settings = Settings()


@lru_cache
def get_settings() -> Settings:
    return settings