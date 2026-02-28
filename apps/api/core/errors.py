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
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


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


def _build_problem_detail(
    status: int,
    title: str,
    detail: str,
    error_type: str = "about:blank",
    instance: str = "",
    request_id: str = "",
) -> dict:
    """Build RFC 7807 Problem Details response body."""
    body = {
        "type": error_type,
        "title": title,
        "status": status,
        "detail": detail,
    }
    if instance:
        body["instance"] = instance
    if request_id:
        body["request_id"] = request_id
    return body


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
        request_id = getattr(request.state, "request_id", "")
        body = _build_problem_detail(
            status=exc.status_code,
            title=title,
            detail=exc.detail,
            error_type=exc.error_type,
            instance=str(request.url.path),
            request_id=request_id,
        )
        return JSONResponse(status_code=exc.status_code, content=body)

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        title = _STATUS_TITLES.get(exc.status_code, "Error")
        detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
        request_id = getattr(request.state, "request_id", "")
        body = _build_problem_detail(
            status=exc.status_code,
            title=title,
            detail=detail,
            instance=str(request.url.path),
            request_id=request_id,
        )
        return JSONResponse(status_code=exc.status_code, content=body)

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "")
        body = _build_problem_detail(
            status=500,
            title="Internal Server Error",
            detail="An unexpected error occurred",
            instance=str(request.url.path),
            request_id=request_id,
        )
        return JSONResponse(status_code=500, content=body)
