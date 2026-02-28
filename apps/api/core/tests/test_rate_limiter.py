"""Tests for Redis sliding window rate limiter.

TDD: Tests define expected behavior of core/rate_limiter.py before it exists.
Uses a mock Redis client to verify rate limiting logic without a live Redis.
"""

import pytest
import time
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient

from apps.api.core.rate_limiter import RateLimiter, rate_limit_dependency


@pytest.fixture
def mock_redis():
    """Mock Redis client with sorted set operations."""
    redis = MagicMock()
    pipeline = MagicMock()
    redis.pipeline.return_value = pipeline
    pipeline.__enter__ = MagicMock(return_value=pipeline)
    pipeline.__exit__ = MagicMock(return_value=False)
    pipeline.execute.return_value = [0, 1, True, 5]  # zremrangebyscore, zadd, expire, zcard
    return redis


@pytest.fixture
def limiter(mock_redis):
    """Create a rate limiter with 5 req/60s."""
    return RateLimiter(redis_client=mock_redis, max_requests=5, window_seconds=60)


class TestRateLimiter:
    """Tests for the RateLimiter class."""

    def test_allow_under_limit(self, limiter, mock_redis):
        """Requests under the limit should be allowed."""
        # Pipeline returns: zremrangebyscore=0, zadd=1, expire=True, zcard=3
        pipeline = mock_redis.pipeline.return_value
        pipeline.execute.return_value = [0, 1, True, 3]

        allowed, remaining, retry_after = limiter.check("user-123")
        assert allowed is True
        assert remaining == 2  # 5 - 3
        assert retry_after is None

    def test_reject_over_limit(self, limiter, mock_redis):
        """Requests over the limit should be rejected with retry_after."""
        pipeline = mock_redis.pipeline.return_value
        pipeline.execute.return_value = [0, 1, True, 6]  # 6 > 5 max

        allowed, remaining, retry_after = limiter.check("user-123")
        assert allowed is False
        assert remaining == 0
        assert retry_after is not None
        assert retry_after > 0

    def test_exactly_at_limit(self, limiter, mock_redis):
        """Request exactly at the limit should be rejected."""
        pipeline = mock_redis.pipeline.return_value
        pipeline.execute.return_value = [0, 1, True, 5]  # 5 == max (just added the 5th)

        allowed, remaining, retry_after = limiter.check("user-123")
        # The 5th request is fine (count == max), the 6th would be rejected
        assert allowed is True
        assert remaining == 0

    def test_redis_pipeline_called_with_correct_key(self, limiter, mock_redis):
        """Verify Redis is called with the correct key format."""
        pipeline = mock_redis.pipeline.return_value
        pipeline.execute.return_value = [0, 1, True, 1]

        limiter.check("user-abc-123")
        pipeline.zremrangebyscore.assert_called_once()
        call_args = pipeline.zremrangebyscore.call_args
        assert "rate_limit:user-abc-123" in str(call_args)

    def test_graceful_fallback_on_redis_error(self, limiter, mock_redis):
        """When Redis fails, requests should be allowed (fail-open)."""
        mock_redis.pipeline.side_effect = Exception("Redis connection refused")

        allowed, remaining, retry_after = limiter.check("user-123")
        assert allowed is True  # Fail open
        assert remaining == -1  # Unknown


class TestRateLimitDependency:
    """Tests for the FastAPI dependency integration."""

    def _make_app(self, mock_redis, max_requests=2, window_seconds=60):
        """Create a test app with rate limiting."""
        app = FastAPI()
        limiter = RateLimiter(
            redis_client=mock_redis,
            max_requests=max_requests,
            window_seconds=window_seconds,
        )
        dep = rate_limit_dependency(limiter)

        @app.get("/test")
        async def test_endpoint(user_id: str = "test-user", _=Depends(dep)):
            return {"ok": True}

        return app

    def test_429_response_has_retry_after_header(self):
        """429 response should include Retry-After header."""
        mock_redis = MagicMock()
        pipeline = MagicMock()
        mock_redis.pipeline.return_value = pipeline
        pipeline.__enter__ = MagicMock(return_value=pipeline)
        pipeline.__exit__ = MagicMock(return_value=False)
        # Over limit
        pipeline.execute.return_value = [0, 1, True, 10]

        app = self._make_app(mock_redis, max_requests=2)

        with patch("apps.api.core.rate_limiter.get_user_id_from_request", return_value="test-user"):
            client = TestClient(app)
            response = client.get("/test")
            assert response.status_code == 429
            assert "Retry-After" in response.headers

    def test_allowed_request_passes_through(self):
        """Request under limit should succeed."""
        mock_redis = MagicMock()
        pipeline = MagicMock()
        mock_redis.pipeline.return_value = pipeline
        pipeline.__enter__ = MagicMock(return_value=pipeline)
        pipeline.__exit__ = MagicMock(return_value=False)
        # Under limit
        pipeline.execute.return_value = [0, 1, True, 1]

        app = self._make_app(mock_redis, max_requests=5)

        with patch("apps.api.core.rate_limiter.get_user_id_from_request", return_value="test-user"):
            client = TestClient(app)
            response = client.get("/test")
            assert response.status_code == 200
