"""RFC 7807 Problem Details error handling.

Provides centralized exception handling middleware and custom exception
classes. All errors return a consistent JSON format:

    {
        "type": "about:blank",
        "title": "Not Found",
        "status": 404,
        "detail": "Transaction xyz not found",
        "instance": "/api/v1/transactions/xyz"
    }

Fixes ARCH-02: replaces ad-hoc error handling across routers.
Upgraded to RFC 9457 Problem Details schema in API-1.
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from apps.api.core.problem_detail import problem_response, PROBLEM_TYPES
from apps.api.core.logging_config import get_request_id_from_state


class AppError(Exception):
    """Base application error."""

    def __init__(self, detail: str, status_code: int = 500, error_type: str = "about:blank"):
        self.detail = detail
        self.status_code = status_code
        self.error_type = error_type
        super().__init__(detail)


class NotFoundError(AppError):
    """Resource not found."""

    def __init__(self, detail: str = "Resource not found"):
        super().__init__(detail=detail, status_code=404)


class ValidationError(AppError):
    """Request validation failed."""

    def __init__(self, detail: str = "Validation failed"):
        super().__init__(detail=detail, status_code=422)


class AuthenticationError(AppError):
    """Authentication failed."""

    def __init__(self, detail: str = "Authentication required"):
        super().__init__(detail=detail, status_code=401)


class RateLimitError(AppError):
    """Rate limit exceeded."""

    def __init__(self, detail: str = "Rate limit exceeded", retry_after: int = 60):
        super().__init__(detail=detail, status_code=429)
        self.retry_after = retry_after


# HTTP status code to title mapping
_STATUS_TITLES = {
    400: "Bad Request",
    401: "Unauthorized",
    403: "Forbidden",
    404: "Not Found",
    409: "Conflict",
    422: "Unprocessable Entity",
    429: "Too Many Requests",
    500: "Internal Server Error",
    502: "Bad Gateway",
    503: "Service Unavailable",
}


def register_error_handlers(app: FastAPI) -> None:
    """Register global exception handlers on the FastAPI app."""

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        title = _STATUS_TITLES.get(exc.status_code, "Error")
        return problem_response(
            status_code=exc.status_code,
            title=title,
            detail=exc.detail,
            type=exc.error_type,
            instance=str(request.url.path),
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        title = _STATUS_TITLES.get(exc.status_code, "Error")
        detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
        return problem_response(
            status_code=exc.status_code,
            title=title,
            detail=detail,
            instance=str(request.url.path),
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        return problem_response(
            status_code=500,
            title="Internal Server Error",
            detail="An unexpected error occurred",
            type=PROBLEM_TYPES.get("internal_error", "about:blank"),
            instance=str(request.url.path),
        )
