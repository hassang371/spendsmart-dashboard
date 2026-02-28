import time

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from apps.api.core.middleware.request_id import get_request_id

logger = structlog.get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware that logs incoming requests and outgoing responses
    with execution duration and structured data (method, path, status).
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        start_time = time.perf_counter()
        req_id = get_request_id()

        # Bind attributes to the context for this specific request
        log = logger.bind(
            request_id=req_id,
            method=request.method,
            path=request.url.path,
        )

        try:
            response = await call_next(request)
            duration_ms = (time.perf_counter() - start_time) * 1000

            log.info(
                "http_request_finished",
                status_code=response.status_code,
                duration_ms=round(duration_ms, 2)
            )
            return response
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            log.error(
                "http_request_failed",
                error=str(e),
                duration_ms=round(duration_ms, 2)
            )
            raise e
