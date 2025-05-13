import uuid
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from typing import Callable

from app.core.request_context import set_request_id

class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Middleware that adds a unique request ID to each request.
    
    This ID is added to response headers and made available in the
    request context for logging and tracing purposes.
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Check if request already has an ID (e.g., from a load balancer or gateway)
        request_id = request.headers.get("X-Request-ID")
        
        # If not, generate a new UUID
        if not request_id:
            request_id = str(uuid.uuid4())
        
        # Store in context var for access in route handlers and loggers
        token = set_request_id(request_id)
        
        # Add ID to request state for potential use in route handlers
        request.state.request_id = request_id
        
        # Process the request and get the response
        response = await call_next(request)
        
        # Add the request ID to the response headers
        response.headers["X-Request-ID"] = request_id
        
        # Reset the context variable token (though usually not necessary due to task context isolation)
        # ctx_token.reset(token)
        
        return response 