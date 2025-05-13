from fastapi import FastAPI, Request, status, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
import logging

from app.core.config import settings
from app.core.redis_client import init_app_redis_pool, close_app_redis_pool
from app.api.health import router as health_router
from app.core.schemas.errors import ErrorResponse, ErrorDetail, ErrorSource, ErrorMeta
from app.core.middleware.security_headers import SecurityHeadersMiddleware
from app.core.middleware.request_id_middleware import RequestIDMiddleware
from app.core.logging_config import setup_logging

# Set up structured logging
setup_logging()

app = FastAPI(
    title=settings.APP_NAME,
    debug=settings.DEBUG_MODE,
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
    docs_url=f"{settings.API_V1_PREFIX}/docs",
    redoc_url=f"{settings.API_V1_PREFIX}/redoc",
)

# Set up middlewares
# Request ID middleware should be first to ensure request_id is available for all other middleware
app.add_middleware(RequestIDMiddleware)

# Security headers middleware
app.add_middleware(SecurityHeadersMiddleware)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[str(origin) for origin in settings.CORS_ALLOWED_ORIGINS],  # Handles Pydantic AnyUrl
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition", "X-Request-ID"]  # Example of exposing custom headers
)

# Custom exception handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Custom handler for Pydantic's RequestValidationError to fit the standard error format.
    """
    field_errors = {}
    for error in exc.errors():
        # Extract field name from location tuple (skipping body, query, or path)
        location_tuple = error.get("loc", ())
        if len(location_tuple) > 1:
            field_key_parts = [str(loc_part) for loc_part in location_tuple[1:]]
            field_key = ".".join(field_key_parts) if field_key_parts else "general"
        elif len(location_tuple) == 1:
            field_key = str(location_tuple[0])
        else:
            field_key = "unknown_field"

        if field_key not in field_errors:
            field_errors[field_key] = []
        field_errors[field_key].append(error["msg"])

    # Determine source pointer or parameter
    first_error_loc = exc.errors()[0].get("loc") if exc.errors() else None
    source_pointer = None
    source_parameter = None
    if first_error_loc:
        if first_error_loc[0] == 'body':
            source_pointer = "/" + "/".join(str(loc) for loc in first_error_loc)
        elif first_error_loc[0] in ('query', 'path'):
            source_parameter = str(first_error_loc[1]) if len(first_error_loc) > 1 else str(first_error_loc[0])

    error_detail = ErrorDetail(
        status=str(status.HTTP_422_UNPROCESSABLE_ENTITY),
        code="validation_error",
        detail="One or more validation errors occurred. Please check the 'field_errors' for details.",
        source=ErrorSource(pointer=source_pointer, parameter=source_parameter) if (source_pointer or source_parameter) else None,
        meta=ErrorMeta(field_errors=field_errors)
    )
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=ErrorResponse(errors=[error_detail]).model_dump(exclude_none=True),
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """
    Custom handler for HTTPException to fit the standard error format.
    """
    meta = None
    if exc.status_code == 405 and hasattr(exc, "headers") and "allow" in exc.headers:
        allowed_methods = exc.headers["allow"].split(", ")
        meta = ErrorMeta(allowed_methods=allowed_methods)
    
    error_detail = ErrorDetail(
        status=str(exc.status_code),
        code=getattr(exc, "error_code", "http_exception"),
        detail=exc.detail,
        meta=meta
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(errors=[error_detail]).model_dump(exclude_none=True),
        headers=getattr(exc, "headers", None),
    )

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """
    Generic exception handler for all unhandled exceptions to provide a consistent error response.
    """
    # Log the exception with the request_id
    logging.exception(f"Unhandled exception: {str(exc)}")
    
    error_detail = ErrorDetail(
        status=str(status.HTTP_500_INTERNAL_SERVER_ERROR),
        code="internal_server_error",
        detail="An unexpected internal server error occurred."
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(errors=[error_detail]).model_dump(exclude_none=True)
    )

# Application startup event
@app.on_event("startup")
async def on_startup():
    """Initialize connections and resources on application startup."""
    # Initialize Redis connection pool
    await init_app_redis_pool()
    # Additional startup tasks could be added here

# Application shutdown event
@app.on_event("shutdown")
async def on_shutdown():
    """Clean up connections and resources on application shutdown."""
    # Close Redis connection pool
    await close_app_redis_pool()
    # Additional cleanup tasks could be added here

# Include routers
app.include_router(health_router, prefix=settings.API_V1_PREFIX)

@app.get("/")
async def root():
    """Root endpoint that redirects to the API documentation."""
    return {
        "message": f"Welcome to {settings.APP_NAME}",
        "documentation": f"{settings.API_V1_PREFIX}/docs"
    }