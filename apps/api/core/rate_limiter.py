"""Redis sliding window rate limiter.

Fixes BUG-05: Replaces the old in-memory defaultdict(deque) rate limiter
with a Redis-backed sliding window using sorted sets.

- Per-user rate limiting keyed by user_id
- Fail-closed in production: if Redis is unavailable mid-request, requests are rejected
- Fail-open in development: if Redis is unavailable mid-request, requests are allowed
- Returns 429 Too Many Requests with Retry-After header when limit exceeded
"""

import hashlib
import time
from typing import Optional, Tuple

import structlog
from fastapi import HTTPException, Request

logger = structlog.get_logger()


def get_user_id_from_request(request: Request) -> str:
    """Extract a rate-limit key from the request.

    BUG-031 fix: Using the last 16 chars of a JWT is collision-prone
    because two distinct tokens can share the same suffix.
    We now use a SHA-256 hash of the full bearer token for a
    stable, collision-free rate limit key with no PII leakage.
    Falls back to client IP if no auth header is present.
    """
    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer ") and len(auth) > 20:
        token = auth[7:]  # strip "Bearer " prefix
        # Truncate to 32 hex chars (128 bits) — more than enough for uniqueness
        token_hash = hashlib.sha256(token.encode()).hexdigest()[:32]
        return f"jwt:{token_hash}"
    # Fallback to IP
    return f"ip:{request.client.host if request.client else 'unknown'}"


class RateLimiter:
    """Redis sliding window rate limiter using sorted sets.

    Algorithm:
    1. Remove entries outside the window (ZREMRANGEBYSCORE)
    2. Add the current timestamp (ZADD)
    3. Set TTL on the key (EXPIRE)
    4. Count entries in the window (ZCARD)
    5. If count > max_requests: reject with Retry-After

    All operations are pipelined for a single round-trip.
    """

    def __init__(self, redis_client, max_requests: int = 60, window_seconds: int = 60):
        self.redis = redis_client
        self.max_requests = max_requests
        self.window_seconds = window_seconds

    def check(self, user_id: str) -> Tuple[bool, int, Optional[int]]:
        """Check if a request is allowed for this user.

        Args:
            user_id: Unique identifier for rate limit bucket.

        Returns:
            Tuple of (allowed, remaining_requests, retry_after_seconds).
            - allowed: True if request is within limits.
            - remaining: Number of requests remaining in window (-1 if unknown).
            - retry_after: Seconds until the window resets (None if allowed).
        """
        try:
            now = time.time()
            window_start = now - self.window_seconds
            key = f"rate_limit:{user_id}"

            pipe = self.redis.pipeline()
            pipe.zremrangebyscore(key, 0, window_start)
            pipe.zadd(key, {str(now): now})
            pipe.expire(key, self.window_seconds)
            pipe.zcard(key)
            results = pipe.execute()

            current_count = results[3]

            if current_count > self.max_requests:
                retry_after = int(self.window_seconds)
                return False, 0, retry_after

            remaining = max(0, self.max_requests - current_count)
            return True, remaining, None

        except Exception as e:
            logger.warning("rate_limit_redis_error", error=str(e), user_id=user_id)
            import os

            if os.getenv("ENVIRONMENT", "development") == "production":
                # Fail-closed in production: reject when Redis is unavailable
                return False, 0, self.window_seconds
            # Fail-open in development: allow request to avoid blocking local dev
            return True, -1, None


def rate_limit_dependency(limiter: RateLimiter):
    """Create a FastAPI dependency that enforces rate limiting.

    Usage:
        limiter = RateLimiter(redis_client=redis, max_requests=60, window_seconds=60)
        dep = rate_limit_dependency(limiter)

        @router.get("/endpoint")
        async def my_endpoint(_=Depends(dep)):
            ...
    """

    async def _check_rate_limit(request: Request):
        user_id = get_user_id_from_request(request)
        allowed, remaining, retry_after = limiter.check(user_id)

        if not allowed:
            raise HTTPException(
                status_code=429,
                detail="Too many requests. Please try again later.",
                headers={"Retry-After": str(retry_after)},
            )

    return _check_rate_limit
