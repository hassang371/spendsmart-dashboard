import contextvars
import uuid
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

# Context variable to store the request ID for the current async context
request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")

def get_request_id() -> str:
    """Read the current request ID from contextvars."""
    return request_id_var.get()


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Middleware that reads an X-Request-ID header or generates a new UUID4,
    stores it in contextvars, and appends it to the response headers.
    """
    
    def __init__(self, app, header_name: str = "X-Request-ID"):
        super().__init__(app)
        self.header_name = header_name

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        req_id: Optional[str] = request.headers.get(self.header_name)
        if not req_id:
            req_id = str(uuid.uuid4())
            
        # Store it for the current execution context
        token = request_id_var.set(req_id)
        
        try:
            response = await call_next(request)
            # Add it to the outgoing response if not already present
            if self.header_name not in response.headers:
                response.headers[self.header_name] = req_id
            return response
        finally:
            request_id_var.reset(token)
