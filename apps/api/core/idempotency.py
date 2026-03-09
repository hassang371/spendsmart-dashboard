"""Idempotency middleware/dependency.

Ensures mutations (like batch categorization or training trigger)
with the same Idempotency-Key header are executed exactly once
within a 24-hour window, returning the cached response for duplicates.
"""

import hashlib
import json
import os
from typing import Any, Callable

import redis.asyncio as redis
from fastapi import Depends, Header, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import structlog

from apps.api.core.auth import get_current_user

logger = structlog.get_logger()

# Use the same Redis instance configured for rate limiting/celery
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
try:
    _redis_client = redis.from_url(REDIS_URL, decode_responses=True)
except Exception:
    _redis_client = None

IDEMPOTENCY_TTL_SECONDS = 24 * 60 * 60  # 24 hours


async def get_idempotency_key(
    request: Request,
    idempotency_key: str | None = Header(
        default=None,
        alias="Idempotency-Key",
        description="Optional idempotent key to prevent duplicate mutations.",
    ),
    current_user = Depends(get_current_user)
) -> str | None:
    """Dependency to extract and validate the idempotency key.

    Returns the namespaced cache key if provided, or None.
    """
    if not idempotency_key:
        return None

    user_id = current_user.id
    
    # Hash the raw payload body if available to bind the key strictly to the content
    # For many routes taking JSON bodies, we can hash the body bytes.
    # However, since FastAPI consumes the stream when parsing, we just use the raw string key
    # along with the user ID and path.
    
    # Create a unique namespace for this key
    fingerprint = hashlib.sha256(f"{user_id}:{request.url.path}:{idempotency_key}".encode()).hexdigest()
    return f"idempotency:{fingerprint}"


async def with_idempotency(
    cache_key: str | None,
    execute_mutation: Callable,
) -> Any:
    """Execute a mutation idempotently if a cache key is provided.
    
    Usage:
        @router.post("/batch")
        async def batch_update(
            key: str | None = Depends(get_idempotency_key),
        ):
            async def run_update():
                # Perform DB update
                return {"updated": 100}
                
            return await with_idempotency(key, run_update)
    """
    if not cache_key or not _redis_client:
        return await execute_mutation()

    # 1. Check for cached response
    try:
        cached_raw = await _redis_client.get(cache_key)
        if cached_raw:
            logger.info("idempotency_cache_hit", cache_key=cache_key)
            data = json.loads(cached_raw)
            # Support extracting status code if we wrap the response
            if isinstance(data, dict) and "__idempotency_status" in data:
                status = data.pop("__idempotency_status")
                return JSONResponse(status_code=status, content=data)
            return data
    except Exception as e:
        logger.warning("idempotency_read_failed", error=str(e))

    # 2. Add 'in_progress' marker to prevent concurrent execution races
    try:
        # Use SETNX (set if not exists)
        set_nx = await _redis_client.set(
            cache_key,
            json.dumps({"__idempotency_in_progress": True}),
            ex=60, # 1 minute timeout for the operation to complete
            nx=True
        )
        if not set_nx:
            # Another request is currently processing this idempotency key
            raise HTTPException(
                status_code=409,
                detail="A request with this Idempotency-Key is already in progress.",
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("idempotency_lock_failed", error=str(e))

    # 3. Execute the actual mutation
    response_data = await execute_mutation()

    # 4. Cache the successful result
    try:
        # Convert response into serializable dict
        if isinstance(response_data, BaseModel):
            store_data = response_data.model_dump()
        elif isinstance(response_data, dict):
            store_data = response_data.copy()
        else:
            store_data = {"result": str(response_data)}

        await _redis_client.set(
            cache_key,
            json.dumps(store_data),
            ex=IDEMPOTENCY_TTL_SECONDS,
        )
        logger.info("idempotency_cache_saved", cache_key=cache_key)
    except Exception as e:
        logger.warning("idempotency_write_failed", error=str(e))

    return response_data
