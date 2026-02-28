"""Tests for core config module."""

import pytest


class TestSettings:
    """Test Pydantic Settings loads env vars correctly."""

    def test_settings_loads_supabase_url(self, monkeypatch):
        """Settings should load SUPABASE_URL from env."""
        monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
        monkeypatch.setenv("SUPABASE_ANON_KEY", "test-anon-key")

        from apps.api.core.config import Settings
        settings = Settings()
        assert settings.SUPABASE_URL == "https://test.supabase.co"

    def test_settings_loads_allowed_origins(self, monkeypatch):
        """Settings should parse ALLOWED_ORIGINS as comma-separated list."""
        monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
        monkeypatch.setenv("SUPABASE_ANON_KEY", "test-anon-key")
        monkeypatch.setenv("ALLOWED_ORIGINS", "http://localhost:3000,https://scale-app.com")

        from apps.api.core.config import Settings
        settings = Settings()
        assert settings.allowed_origins == [
            "http://localhost:3000",
            "https://scale-app.com",
        ]

    def test_settings_defaults(self, monkeypatch):
        """Settings should have sensible defaults."""
        monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
        monkeypatch.setenv("SUPABASE_ANON_KEY", "test-anon-key")

        from apps.api.core.config import Settings
        settings = Settings()
        assert settings.LOG_LEVEL == "INFO"
        assert settings.ENVIRONMENT == "development"
        assert settings.ALLOWED_ORIGINS == "http://localhost:3000"
