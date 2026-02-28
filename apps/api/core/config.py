"""Centralized application configuration via Pydantic Settings.

Loads all env vars into a typed Settings instance. Replaces scattered
os.environ.get() calls throughout the codebase.
"""

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Supabase
    SUPABASE_URL: str = Field(..., description="Supabase project URL")
    SUPABASE_ANON_KEY: str = Field(..., description="Supabase anon/public key")
    SUPABASE_SERVICE_KEY: str = Field(
        default="",
        description="Supabase service-role key (for Celery worker)",
    )

    # CORS
    ALLOWED_ORIGINS: str = Field(
        default="http://localhost:3000",
        description="Comma-separated allowed origins for CORS",
    )

    # Redis
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL",
    )

    # Logging
    LOG_LEVEL: str = Field(default="INFO", description="Python log level")
    ENVIRONMENT: str = Field(
        default="development",
        description="Runtime environment: development, staging, production",
    )

    # App
    APP_VERSION: str = Field(default="0.3.0", description="Application version")

    # Sentry (optional)
    SENTRY_DSN: str = Field(default="", description="Sentry DSN for error tracking")

    @property
    def allowed_origins(self) -> list[str]:
        """Parse comma-separated origins into a list."""
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

    @property
    def log_level(self) -> str:
        return self.LOG_LEVEL

    model_config = {"env_file": ".env", "extra": "ignore"}


def get_settings() -> Settings:
    """Factory for Settings — allows test override."""
    return Settings()


# Module-level singleton (lazy: only created when first accessed)
try:
    settings = get_settings()
except Exception:
    # During testing, env vars may not be set — defer to test fixtures
    settings = None  # type: ignore[assignment]

