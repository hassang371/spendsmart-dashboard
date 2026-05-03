"""Metrics endpoints — Prometheus exposition + client-event telemetry.

Two routes:

* ``GET /metrics/prom`` — Prometheus exposition of the RFC-004
  ``CollectorRegistry`` set up in ``apps/api/core/metrics.py``.
  Unauthenticated; behind the internal-VPC / scrape-allowlist per the
  ops runbook.
* ``POST /api/v1/metrics/client-event`` — JWT-authenticated +
  rate-limited (30/min/user) telemetry route per RFC-004 §Codex Fix #4.
  Accepts ``{event: "forecast_warm_outcome", result: ...}`` and
  increments ``forecast_warm_outcome_total{result}``.

The ``client-event`` route is mounted under the same ``/api/v1`` prefix
as the rest of the domain routers; the Prometheus exposition route is
mounted at the application root because Prometheus scrape configs
expect a stable, prefix-free path.

Refs: docs/rfcs/RFC-004-tft-inference-cache-architecture.md §8 + §Codex Fix #4
"""

from __future__ import annotations

from typing import Literal

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel, Field

from apps.api.core.auth import get_current_user_id
from apps.api.core.metrics import REGISTRY, forecast_warm_outcome_total

logger = structlog.get_logger()

# Public exposition endpoint — no auth, no /api/v1 prefix because
# scrape configs hard-code the path. Mounted on the FastAPI app
# directly (see apps/api/main.py).
prom_router = APIRouter(tags=["metrics"])


@prom_router.get("/metrics/prom")
async def metrics_prom() -> Response:
    """Prometheus exposition of the RFC-004 ``CollectorRegistry``."""
    return Response(
        content=generate_latest(REGISTRY),
        media_type=CONTENT_TYPE_LATEST,
    )


# JWT-authenticated client-event router — under /api/v1 prefix.
client_event_router = APIRouter(prefix="/metrics", tags=["metrics"])


_VALID_RESULTS = ("ok", "429", "timeout", "error")
_VALID_EVENTS = ("forecast_warm_outcome",)


class ClientEvent(BaseModel):
    """Telemetry envelope posted by the frontend.

    The only event accepted today is ``forecast_warm_outcome``; the
    server rejects unknown event names with HTTP 400 to keep the
    Prometheus label cardinality bounded.
    """

    event: Literal["forecast_warm_outcome"] = Field(
        ..., description="Event identifier — only forecast_warm_outcome is accepted today."
    )
    result: Literal["ok", "429", "timeout", "error"] = Field(..., description="Outcome label for the event.")


def _client_event_rate_limit(request: Request):
    """Resolve the per-app client-event rate-limit dependency.

    The dependency object itself is constructed once in the FastAPI
    lifespan (``app.state.client_event_rate_limiter``). This indirection
    matches the existing /ingest/import pattern.
    """
    dep = getattr(request.app.state, "client_event_rate_limiter", None)
    if dep is None:
        return None
    return dep


@client_event_router.post("/client-event", status_code=204)
async def post_client_event(
    payload: ClientEvent,
    request: Request,
    user_id: str = Depends(get_current_user_id),
) -> Response:
    """Increment the ``forecast_warm_outcome_total{result}`` counter.

    Pydantic validation rejects unknown ``event`` and ``result`` values
    with HTTP 422. The route guard below additionally enforces the
    enums explicitly so we get a 400 (per RFC-004 §Codex Fix #4)
    instead of the default 422 — this matches the spec wording:
    "Reject unknown event names with 400."
    """
    # Defence-in-depth: Pydantic Literal[...] should already have
    # caught these, but the spec asks for a 400 on unknown event.
    if payload.event not in _VALID_EVENTS:
        raise HTTPException(status_code=400, detail="Unknown event name.")
    if payload.result not in _VALID_RESULTS:
        raise HTTPException(status_code=400, detail="Unknown result label.")

    # Rate-limit check. We do it after Pydantic validation so the
    # quota is consumed only by well-formed payloads.
    dep = _client_event_rate_limit(request)
    if dep is not None:
        await dep(request)

    forecast_warm_outcome_total.labels(result=payload.result).inc()
    logger.info(
        "client_event_recorded",
        user_id=user_id,
        event_name=payload.event,
        result=payload.result,
    )
    return Response(status_code=204)


__all__ = ["prom_router", "client_event_router"]
