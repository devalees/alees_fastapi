Okay, let's enhance the `api_strategy.md (FastAPI Edition - v2)` by adding the "General Setup Implementation Details" and "Integration & Usage Patterns" sections. I will ensure the RBAC examples and discussion explicitly incorporate organization scoping.

---

**`api_strategy.md` (FastAPI Edition - v2 - WITH NEW SECTIONS)**

# API Design & Development Strategy (FastAPI Edition - v2)

## 1. Overview
    * Purpose: This document outlines the strategy and conventions for designing, developing, and managing the RESTful API for the ERP system using the **FastAPI** framework. Consistency, usability, type safety, automated documentation, security, and performance are key goals.

## 2. API Style
    * Framework: **FastAPI**.
    * Format: **JSON**. Headers `Content-Type: application/json` and `Accept: application/json`.
    * URL Naming: Plural nouns for collections, resource IDs for instances, verbs for actions, underscores for readability.
    * HTTP Methods: Standard usage (`GET`, `POST`, `PUT`, `PATCH`, `DELETE`).
    * Statelessness: API requests must be stateless.
    * Asynchronicity: Leverage `async` and `await`.

## 3. Authentication & Authorization (Strategic Overview)
    * Implemented via FastAPI Dependency Injection.
    * **3.1. JWT:** For UI/interactive clients (`python-jose`, `passlib`). Endpoints: `/api/v1/auth/token/obtain/`, `/api/v1/auth/token/refresh/`. Configurable lifetimes via Pydantic settings.
    * **3.2. API Keys:** For server-to-server. Hashed storage in DB, linked to User, expiry. Transmitted via `X-API-Key` header.
    * **3.3. Authorization (RBAC & Organization Isolation):**
        * Models: `User`, `Role`, `Permission`, `UserRole`, `RolePermission`. Permissions like `product:create`.
        * `rbac_service.check_user_permission_for_org(user, permission_name, organization_id)` centralizes checks.
        * FastAPI dependencies like `require_organization_permission(permission_name, organization_id=Path(...))` enforce this.

## 4. Versioning (Strategic Overview)
    * Strategy: URL Path Versioning (e.g., `/api/v1/...`).
    * Implementation: FastAPI `APIRouter` per version, mounted with a prefix.
    * Deprecation Policy: Defined with headers and communication.

## 5. Standard Response & Error Formats (Strategic Overview)
    * **5.1. Successful Responses:** Paginated lists (using `fastapi-pagination`), full objects for detail/create/update, `204 No Content` for delete, status object for actions. Pagination sizes configurable via Pydantic settings.
    * **5.2. Error Responses:** Standard JSON structure with `errors` list (each error having `status`, `code`, `detail`, optional `source`, `meta`). Implemented via custom FastAPI exception handlers. Predefined application error codes.

## 6. Serialization (Data Input/Output - Strategic Overview)
    * Tool: **Pydantic Models**. Separate models for Create, Update, Read.
    * `model_config = {"from_attributes": True}` for ORM compatibility.
    * Relationships: Nested models for read (controlled depth), IDs for write.
    * Custom Fields (JSON): `Json[StructureModel]` or `Json[Any]` with Pydantic validators.
    * Transformation/Validation: Pydantic `@validator`, `@model_validator`, `computed_field`.

## 7. Rate Limiting (Strategic Overview)
    * Tool: **`slowapi`** with Redis backend.
    * Strategy: Per-user and per-IP limits, configurable via Pydantic settings.
    * Response: `429 Too Many Requests` with `Retry-After`.

## 8. Module-Specific Settings Management via API (Strategic Overview)
    * Dedicated models (e.g., `BillingSettings`), Pydantic schemas, API endpoints (e.g., `/orgs/{org_id}/settings/billing/`), RBAC, caching.

## 9. Development Guidelines (Strategic Overview)
    * Project Structure, Pytest testing, OpenAPI documentation, Security focus, Async code.

## 10. General Setup Implementation Details

    This section details the one-time setup and core configurations for the FastAPI application related to its API structure, error handling, and core dependencies.

    ### 10.1. Library Installation
    *   Ensure core FastAPI and related libraries are in `requirements/base.txt`:
        ```txt
        fastapi>=0.100.0,<0.101.0 # Or latest stable
        uvicorn[standard]>=0.23.0,<0.24.0
        pydantic>=2.0.0,<3.0.0
        pydantic-settings>=2.0.0,<2.2.0
        python-jose[cryptography]>=3.3.0,<3.4.0 # For JWT
        passlib[bcrypt]>=1.7.4,<1.8.0         # For password hashing
        slowapi>=0.1.8,<0.2.0                  # For rate limiting
        fastapi-pagination>=0.12.0,<0.13.0     # For pagination
        # Add email-validator if using Pydantic's EmailStr and want robust validation
        # email-validator>=2.0.0,<2.1.0
        ```

    ### 10.2. Main FastAPI Application Instance (`app/main.py`)
    *   Initialize the FastAPI app.
    *   Mount routers from feature modules.
    *   Set up startup/shutdown events (e.g., for DB pools, Redis pools).
    *   Register custom exception handlers.
    *   Add middleware (e.g., CORS, Prometheus, Sentry).
        ```python
        # app/main.py
        from fastapi import FastAPI, Request, status
        from fastapi.responses import JSONResponse
        from fastapi.exceptions import RequestValidationError
        from fastapi.middleware.cors import CORSMiddleware
        # from starlette.exceptions import HTTPException as StarletteHTTPException # If needed for specific global handler

        from app.core.config import settings
        from app.core.db import init_db_engine, close_db_engine # If you have explicit init/close
        from app.core.redis_client import init_app_redis_pool, close_app_redis_pool
        from app.api.v1 import api_router as v1_api_router # Example v1 router
        # Import your custom exception Pydantic models (ErrorDetail, ErrorResponse)
        from app.core.schemas.errors import ErrorResponse, ErrorDetail # Assuming you create these

        # Define custom exception handlers (as per API Strategy Section 5.2)
        async def pydantic_validation_exception_handler(request: Request, exc: RequestValidationError):
            # ... (Implementation to format Pydantic errors into ErrorResponse)
            # See API Strategy document for example implementation
            field_errors = {}
            for error in exc.errors():
                field_name = ".".join(str(loc) for loc in error["loc"] if loc not in ('body', 'query', 'path')) or "general"
                if field_name not in field_errors: field_errors[field_name] = []
                field_errors[field_name].append(error["msg"])
            
            error_obj = ErrorDetail(
                status=str(status.HTTP_422_UNPROCESSABLE_ENTITY),
                code="validation_error",
                detail="Input validation failed.",
                meta={"field_errors": field_errors}
            )
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                content=ErrorResponse(errors=[error_obj]).model_dump(exclude_none=True)
            )

        # General HTTPException handler (for custom HTTPExceptions you raise)
        async def custom_http_exception_handler(request: Request, exc: HTTPException):
             error_obj = ErrorDetail(
                status=str(exc.status_code),
                code=getattr(exc, "error_code", "http_exception"), # Add 'error_code' to your custom HTTPExceptions
                detail=exc.detail,
                # meta logic for allowed_methods if exc.status_code == 405
            )
             return JSONResponse(
                status_code=exc.status_code,
                content=ErrorResponse(errors=[error_obj]).model_dump(exclude_none=True),
                headers=getattr(exc, "headers", None),
            )
        
        # Generic 500 error handler
        async def generic_exception_handler(request: Request, exc: Exception):
            # Log the exception for debugging (Sentry will also capture this if configured)
            # logger.error("Unhandled exception", exc_info=exc)
            error_obj = ErrorDetail(
                status=str(status.HTTP_500_INTERNAL_SERVER_ERROR),
                code="internal_server_error",
                detail="An unexpected internal server error occurred."
            )
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content=ErrorResponse(errors=[error_obj]).model_dump(exclude_none=True)
            )

        app = FastAPI(
            title=settings.APP_NAME,
            openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
            # Add other FastAPI app parameters like version, description
        )

        # Middleware
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[str(origin) for origin in settings.CORS_ALLOWED_ORIGINS], # Handles Pydantic AnyUrl
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        # app.add_middleware(PrometheusMiddleware) # If using starlette-prometheus
        # Sentry ASGI middleware is added automatically by sentry_sdk.init if fastapi integration is used

        # Exception Handlers
        app.add_exception_handler(RequestValidationError, pydantic_validation_exception_handler)
        app.add_exception_handler(HTTPException, custom_http_exception_handler) # Handles FastAPI's HTTPException
        # app.add_exception_handler(StarletteHTTPException, custom_http_exception_handler) # If you need to catch Starlette's one too
        app.add_exception_handler(Exception, generic_exception_handler) # Catch-all for 500s


        # Startup/Shutdown Events
        @app.on_event("startup")
        async def on_startup():
            # await init_db_engine() # If your db module has one
            await init_app_redis_pool()
            # Initialize other resources (e.g., ES client, feature flag service connection)

        @app.on_event("shutdown")
        async def on_shutdown():
            # await close_db_engine()
            await close_app_redis_pool()
            # Close other resources

        # Mount API Routers
        app.include_router(v1_api_router, prefix=settings.API_V1_PREFIX)
        # Add pagination utility
        # from fastapi_pagination import add_pagination
        # add_pagination(app)

        # Root endpoint (optional)
        @app.get("/", tags=["Root"])
        async def read_root():
            return {"message": f"Welcome to {settings.APP_NAME}"}

        ```

    ### 10.3. Core Authentication Dependencies (`app/core/auth_dependencies.py`)
    *   Implement `get_current_active_user` (for JWT) and `verify_api_key` dependencies. These will use utilities from `app/core/security.py` (for JWT processing, password hashing) and database services (for user lookup, API key lookup).
        ```python
        # app/core/auth_dependencies.py (Conceptual Structure)
        # from fastapi import Depends, HTTPException, status, Security
        # from fastapi.security import OAuth2PasswordBearer, APIKeyHeader
        # from jose import JWTError, jwt
        # from pydantic import ValidationError
        # from app.core.config import settings
        # from app.core.db import get_db_session
        # from app.features.users.services import user_service # Example user service
        # from app.features.users.schemas import UserRead # Example user Pydantic schema
        # from app.core.security import ALGORITHM, decode_access_token # Your security utils

        # oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_PREFIX}/auth/token/obtain")
        # api_key_header_auth = APIKeyHeader(name="X-API-Key", auto_error=False)

        # async def get_current_user_from_token(
        #     db: AsyncSession = Depends(get_db_session), token: str = Depends(oauth2_scheme)
        # ) -> UserRead:
        #     payload = decode_access_token(token) # This function handles expiry and signature
        #     if payload is None or payload.get("sub") is None:
        #         raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token subject", headers={"WWW-Authenticate": "Bearer"})
        #     user_id = payload["sub"]
        #     # user = await user_service.get_user_by_id(db, user_id=int(user_id))
        #     # if user is None:
        #     #     raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found", headers={"WWW-Authenticate": "Bearer"})
        #     # return UserRead.from_orm(user) # Assuming from_orm or model_validate
        #     pass # Replace with actual implementation

        # async def get_current_active_user(current_user: UserRead = Depends(get_current_user_from_token)) -> UserRead:
        #     # if not current_user.is_active: # Assuming an is_active field
        #     #     raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user")
        #     return current_user

        # async def verify_api_key_dependency(
        #    db: AsyncSession = Depends(get_db_session), api_key: str = Security(api_key_header_auth)
        # ) -> UserRead:
        #     if not api_key:
        #         raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authenticated with API Key")
        #     # user = await user_service.get_user_by_api_key(db, api_key) # Service to validate hashed key and get user
        #     # if not user:
        #     #     raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid API Key")
        #     # return UserRead.from_orm(user)
        #     pass # Replace with actual implementation

        # A combined dependency if an endpoint can accept either JWT or API Key
        # async def get_authenticated_user(
        #     # jwt_user: Optional[UserRead] = Depends(get_current_user_optional), # modified get_current_user to not raise if no token
        #     # apikey_user: Optional[UserRead] = Depends(verify_api_key_optional) # modified to not raise if no key
        # ):
        #     # if jwt_user: return jwt_user
        #     # if apikey_user: return apikey_user
        #     # raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
        #     pass
        ```

    ### 10.4. Core RBAC Dependency (`app/core/rbac_dependencies.py`)
    *   Implement the `require_organization_permission` dependency. This will itself depend on an authentication dependency (like `get_current_active_user`) and use the `rbac_service` (to be created, e.g., in `app/features/users/services/rbac_service.py`).
        ```python
        # app/core/rbac_dependencies.py (Conceptual)
        # from fastapi import Depends, HTTPException, status, Path
        # from app.core.auth_dependencies import get_current_active_user # Or a combined auth dep
        # from app.features.users.schemas import UserRead
        # from app.features.users.services import rbac_service # Your RBAC checking service
        # from sqlalchemy.ext.asyncio import AsyncSession
        # from app.core.db import get_db_session

        # def require_organization_permission(permission_name: str):
        #     async def _ R(
        #         current_user: UserRead = Depends(get_current_active_user), # Or get_authenticated_user
        #         organization_id: int = Path(..., description="The ID of the organization for this operation"),
        #         db: AsyncSession = Depends(get_db_session) # If rbac_service needs it
        #     ):
        #         # has_perm = await rbac_service.check_user_permission_for_org(
        #         #    db=db, user_id=current_user.id, permission_name=permission_name, organization_id=organization_id
        #         # )
        #         # if not has_perm:
        #         #     raise HTTPException(
        #         #         status_code=status.HTTP_403_FORBIDDEN,
        #         #         detail="You do not have sufficient permissions for this resource within the specified organization."
        #         #     )
        #         return current_user # Return user for convenience in path op
        #     return _R
        ```

    ### 10.5. Pagination Setup
    *   In `app/main.py`, add `add_pagination(app)` from `fastapi-pagination`.
    *   Configure default and max sizes in `app/core/config.py:Settings`.

    ### 10.6. Rate Limiting Setup (`slowapi`)
    *   In `app/main.py`, initialize `Limiter` from `slowapi` and add its exception handler.
        ```python
        # app/main.py (additions for slowapi)
        # from slowapi import Limiter, _rate_limit_exceeded_handler
        # from slowapi.util import get_remote_address
        # from slowapi.errors import RateLimitExceeded
        # from starlette.requests import Request as StarletteRequest # For get_remote_address

        # limiter = Limiter(key_func=get_remote_address, default_limits=[settings.API_RATE_LIMIT_ANONYMOUS])
        # app.state.limiter = limiter # Make limiter accessible globally if needed, or pass to routers
        # app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
        ```
        *Rate limits per user would require a different `key_func` that uses the authenticated user ID.*

## 11. Integration & Usage Patterns

    This section provides examples of how feature modules will integrate with the core API setup.

    ### 11.1. Structuring Feature Routers (`app/features/<feature_name>/router.py`)
    *   Each feature module will have its own `APIRouter`.
        ```python
        # app/features/products/router.py
        # from fastapi import APIRouter, Depends, HTTPException, status, Path, Query
        # from typing import List, Optional
        # from ..schemas import ProductRead, ProductCreate, ProductUpdate # Feature-specific Pydantic schemas
        # from ..services import product_service # Feature-specific service layer
        # from app.core.db import AsyncSession, get_db_session
        # from app.core.auth_dependencies import get_current_active_user
        # from app.core.rbac_dependencies import require_organization_permission
        # from app.users.schemas import UserRead # For current_user type hint
        # from fastapi_pagination import Page, paginate # For pagination

        # router = APIRouter(tags=["Products"])

        # @router.post(
        #     "/{organization_id}/products/",
        #     response_model=ProductRead,
        #     status_code=status.HTTP_201_CREATED,
        #     dependencies=[Depends(require_organization_permission("product:create"))] # Enforce permission
        # )
        # async def create_product_for_organization(
        #     organization_id: int, # Path param validated by RBAC dep for access
        #     product_in: ProductCreate,
        #     db: AsyncSession = Depends(get_db_session),
        #     # current_user: UserRead = Depends(get_current_active_user) # Already available if RBAC dep returns it
        # ):
        #     # Ensure product_in is associated with organization_id or current_user's org
        #     # return await product_service.create_product(db=db, obj_in=product_in, organization_id=organization_id)
        #     pass

        # @router.get("/{organization_id}/products/", response_model=Page[ProductRead])
        # async def list_products_for_organization(
        #     organization_id: int,
        #     # current_user: UserRead = Depends(require_organization_permission("product:list")),
        #     db: AsyncSession = Depends(get_db_session),
        #     # Add other filter params as Query(...)
        # ):
        #     # products = await product_service.get_products_by_organization(db=db, organization_id=organization_id)
        #     # return paginate(products) # Use fastapi-pagination
        #     pass
        ```

    ### 11.2. Using Authentication and Authorization Dependencies
    *   Apply auth/RBAC dependencies to path operations as shown above.
    *   The `organization_id` in the path is crucial for organization-scoped RBAC. The `require_organization_permission` dependency must verify the `current_user` has the specified permission *for that specific `organization_id`*.

    ### 11.3. Implementing Path Operations
    *   Path operation functions should be `async def`.
    *   They primarily delegate business logic to service layer functions.
    *   Type hint request bodies and `response_model` with Pydantic schemas.
    *   Inject dependencies like `db: AsyncSession`, `current_user: UserRead`, and custom service dependencies.

    ### 11.4. Error Handling in Path Operations
    *   Service layer functions should raise specific custom HTTPExceptions (e.g., `NotFoundError(HTTPException)`) or application exceptions that are then handled by custom exception handlers.
    *   Path operations generally let these exceptions propagate.

    ### 11.5. Applying Rate Limiting to Specific Endpoints (if needed)
    *   Use `slowapi` decorators on path operations if specific endpoints need different limits than the defaults.
        ```python
        # from app.main import limiter # Assuming limiter is globally accessible or passed to router

        # @router.post("/resource-intensive-action")
        # @limiter.limit("5/minute") # Specific limit for this endpoint
        # async def perform_action(request: Request, ...): # request: Request is needed by limiter
        #     pass
        ```

    ### 11.6. Versioning
    *   New versions of the API (e.g., `/v2/`) will involve creating a new set of routers (e.g., `app/api/v2/`) and mounting them in `app/main.py` with the new prefix.

