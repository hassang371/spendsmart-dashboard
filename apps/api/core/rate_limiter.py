"""Redis sliding window rate limiter.

Fixes BUG-05: Replaces the old in-memory defaultdict(deque) rate limiter
with a Redis-backed sliding window using sorted sets.

- Per-user rate limiting keyed by user_id
- Fail-open: if Redis is unavailable, requests are allowed (with a warning)
- Returns 429 Too Many Requests with Retry-After header when limit exceeded
"""

import time
import structlog
from typing import Optional, Tuple

from fastapi import Depends, HTTPException, Request

logger = structlog.get_logger()


def get_user_id_from_request(request: Request) -> str:
    """Extract a rate-limit key from the request.

    Uses the Authorization header's token hash as the key.
    Falls back to client IP if no auth header.
    """
    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer ") and len(auth) > 20:
        # Use last 16 chars of token as key (enough for uniqueness, no PII)
        return f"jwt:{auth[-16:]}"
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
            # Fail-open: allow request if Redis is unavailable
            logger.warning("rate_limit_redis_error", error=str(e), user_id=user_id)
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
