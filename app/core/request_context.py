import contextvars
from typing import Optional

# Context variable to store request_id for each request
request_id_ctx_var = contextvars.ContextVar[Optional[str]]("request_id", default=None)

def get_request_id() -> Optional[str]:
    """Get the current request ID from the context variable."""
    return request_id_ctx_var.get()

def set_request_id(request_id: str) -> None:
    """Set the request ID in the context variable."""
    request_id_ctx_var.set(request_id) 