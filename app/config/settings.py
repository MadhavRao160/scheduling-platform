from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration, read once from the environment at startup.

    Field names are lower-case; the matching environment variables are the
    upper-case form (DATABASE_URL -> database_url), matched case-insensitively.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # No default: a missing DATABASE_URL must stop the process at startup
    # rather than surface as a confusing failure on the first query.
    database_url: str

    environment: Literal["development", "production"] = "development"
    port: int = 8000

    @property
    def is_development(self) -> bool:
        """Whether tracebacks may be exposed in error responses."""
        return self.environment == "development"


settings = Settings()


@lru_cache
def get_settings() -> Settings:
    """FastAPI dependency form. Returns the same instance as the module-level
    `settings`, for handlers that prefer injection over a direct import."""
    return settings