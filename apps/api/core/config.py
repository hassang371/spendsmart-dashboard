"""Centralized application configuration via Pydantic Settings.

Loads all env vars into a typed Settings instance. Replaces scattered
os.environ.get() calls throughout the codebase.
"""

from pydantic import Field
from pydantic_settings import BaseSettings


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
    PRODUCTION_ORIGINS: str = Field(
        default="",
        description="Comma-separated production origins. Overrides ALLOWED_ORIGINS if ENVIRONMENT=production",
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
    APP_VERSION: str = Field(default="0.5.0", description="Application version")

    # Sentry (optional)
    SENTRY_DSN: str = Field(default="", description="Sentry DSN for error tracking")

    # Setu Account Aggregator (optional — 503 if missing when link is attempted)
    SETU_CLIENT_ID: str = Field(default="", description="Setu FIU client ID")
    SETU_CLIENT_SECRET: str = Field(default="", description="Setu FIU client secret")
    SETU_BASE_URL: str = Field(
        default="https://fiu-sandbox.setu.co",
        description="Setu API base URL",
    )
    SETU_AUTH_URL: str = Field(
        default="https://auth-v2.setu.co/realms/setu/protocol/openid-connect/token",
        description="Setu OAuth2 token endpoint (Keycloak)",
    )
    SETU_PRODUCT_INSTANCE_ID: str = Field(
        default="",
        description="Setu product instance ID (x-product-instance-id header)",
    )
    SETU_REDIRECT_URL: str = Field(
        default="http://localhost:3000/dashboard/accounts/callback",
        description="Redirect URL after Setu consent flow",
    )

    @property
    def allowed_origins(self) -> list[str]:
        """Parse comma-separated origins into a list.

        M3 Fix: Enforces strict CORS in production. Triggers warning if * is used.
        """
        import logging

        logger = logging.getLogger(__name__)

        origins_str = (
            self.PRODUCTION_ORIGINS
            if self.ENVIRONMENT == "production" and self.PRODUCTION_ORIGINS
            else self.ALLOWED_ORIGINS
        )
        origins = [o.strip() for o in origins_str.split(",") if o.strip()]

        if self.ENVIRONMENT == "production" and "*" in origins:
            logger.warning("SECURITY RISK: Wildcard (*) CORS origin allowed in production!")

        return origins

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
