from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

class ErrorSource(BaseModel):
    pointer: Optional[str] = None  # JSON Pointer to the field in request body
    parameter: Optional[str] = None  # Name of query/path parameter

class ErrorMeta(BaseModel):
    field_errors: Optional[Dict[str, List[str]]] = None  # Detailed Pydantic field errors
    allowed_methods: Optional[List[str]] = None  # For 405 errors
    # Add other meta fields as needed, e.g., for custom error codes

class ErrorDetail(BaseModel):
    status: str  # HTTP status code as a string
    code: str    # Application-specific error code
    detail: str  # Human-readable general explanation
    source: Optional[ErrorSource] = None
    meta: Optional[ErrorMeta] = None

class ErrorResponse(BaseModel):
    errors: List[ErrorDetail] 