"""Security headers middleware — equivalent to Express helmet() for FastAPI.

Adds defensive HTTP response headers to every response:
- X-Frame-Options: DENY           — prevents clickjacking
- X-Content-Type-Options: nosniff — prevents MIME sniffing
- Strict-Transport-Security       — enforces HTTPS (only on production)
- Referrer-Policy                 — limits referrer info leakage
- Permissions-Policy              — disables unused browser features
- Content-Security-Policy         — restricts resource loading (API only)

The server header is removed to avoid fingerprinting.
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware that adds security headers to every response.

    Args:
        app: The ASGI application.
        production: When True, includes Strict-Transport-Security (HSTS).
                    Set to False in local dev to avoid breaking HTTP.
    """

    def __init__(self, app, production: bool = False):
        super().__init__(app)
        self._production = production

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        # Prevent clickjacking — disallow embedding in frames
        response.headers["X-Frame-Options"] = "DENY"

        # Prevent MIME-type sniffing — browser must honor Content-Type
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Control referrer information sent with cross-origin requests
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Disable browser features the API doesn't need
        response.headers["Permissions-Policy"] = (
            "geolocation=(), microphone=(), camera=(), payment=()"
        )

        # CSP for an API: reject all content, disallow framing
        # Since we serve JSON only (no HTML/scripts), this is very restrictive
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; frame-ancestors 'none'"
        )

        # HSTS: only in production (breaks local HTTP dev if always on)
        if self._production:
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )

        # Remove server header to avoid fingerprinting the framework/version
        # MutableHeaders does not support .pop(); use conditional delete instead
        if "server" in response.headers:
            del response.headers["server"]

        return response
