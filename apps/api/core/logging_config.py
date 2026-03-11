import logging
import sys
import uuid
from typing import Callable

import structlog
from fastapi import Request, Response


def setup_logging(is_dev: bool = False) -> None:
    """Configures structlog for the application. JSON in prod, Console in dev."""

    # We want to use structlog for everything, so intercept standard logging
    # and route it through structlog
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=logging.INFO)

    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if is_dev:
        processors.append(structlog.dev.ConsoleRenderer(colors=True))
    else:
        # Standard JSON logging for production (Datadog/CloudWatch friendly)
        processors.append(structlog.processors.JSONRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


async def structlog_middleware(request: Request, call_next: Callable) -> Response:
    """
    Middleware that generates a unique request_id, adds it to the structlog context,
    and injects it into the response headers.
    """
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))

    # Bind the request_id to all logs emitted during this request cycle
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        request_id=request_id,
        method=request.method,
        path=request.url.path,
        client_ip=request.client.host if request.client else None,
    )

    # Store in state so exception handlers can extract it
    request.state.request_id = request_id

    # Log request start
    logger = structlog.get_logger("api.request")
    logger.info("request_started")

    try:
        response = await call_next(request)

        # Log request end
        logger.info(
            "request_finished",
            status_code=response.status_code,
        )

        response.headers["X-Request-ID"] = request_id
        return response

    except Exception as e:
        logger.exception("request_failed", error=str(e))
        raise


def get_request_id_from_state(request: Request) -> str:
    """Helper to extract request_id safely."""
    return getattr(request.state, "request_id", None)
