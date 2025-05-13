from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from typing import Callable

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY" # Or "SAMEORIGIN"
        # response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; object-src 'none';" # Example CSP, very restrictive
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains" # If site is HTTPS only
        # response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        # response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()" # Disable features by default
        return response 