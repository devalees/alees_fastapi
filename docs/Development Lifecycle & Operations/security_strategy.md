# Security Strategy (FastAPI Edition)

## 1. Overview

    * Purpose: To define the overall strategy, principles, and key practices for ensuring the security of the FastAPI-based ERP system.
    * Scope: Covers secure development practices, dependency management, authentication/authorization implementation, secrets management integration, infrastructure security, data protection, logging, and incident response planning.
    * Goal: Minimize vulnerabilities, protect data, comply with regulations, and build trust via DevSecOps principles.

## 2. Core Security Principles

    * Defense in Depth, Principle of Least Privilege, Secure Defaults, Input Validation (Pydantic), Secure Coding Practices (OWASP), Regular Updates & Patching, Security through Automation, Logging & Monitoring, Assume Breach.

## 3. Secure Development Lifecycle (SDL) (Strategic Overview - already detailed)

    * Threat Modeling, Secure Coding Training, Mandatory Code Reviews (with security focus), Static Analysis (SAST - Bandit, Ruff/Flake8 security plugins), Dependency Scanning (`pip-audit`), Dynamic Analysis (DAST - periodic), Penetration Testing (periodic).

## 4. Authentication & Authorization (Strategic Overview - see `api_strategy.md` for details)

    * **Authentication:** JWT (UI), API Keys (server-to-server). Strong password policies (passlib). Rate limiting on auth endpoints. Future MFA.
    * **Authorization (RBAC):** FastAPI dependencies checking user roles/permissions against resources/actions and organization scope.

## 5. Secrets Management (Strategic Overview - see `secrets_management_strategy.md`)

    * AWS Secrets Manager, injected as environment variables, consumed by Pydantic Settings. No secrets in code/Git.

## 6. Data Security & Input Validation (Strategic Overview - Pydantic focus in `validation_strategy.md`)

    * **Input Validation:** Primarily Pydantic.
    * **Output Encoding:** Frontend responsibility. Backend (Jinja2 for emails) uses auto-escaping.
    * **SQL Injection Prevention:** SQLAlchemy ORM with parameterized queries.
    * **File Uploads:** Validate type/size, secure storage, random names, pre-signed URLs/brokered access, virus scanning (async).
    * **Security Headers:** Middleware for HSTS, X-Content-Type-Options, X-Frame-Options, CSP, etc.
    * **CORS:** FastAPI `CORSMiddleware` with restrictive origin configuration.
    * **CSRF Protection:** Less concern for typical JWT Bearer token APIs; focus on CORS. Not implemented unless specific cookie-based browser form auth is added.
    * **Encryption in Transit:** Mandatory HTTPS (TLS/SSL) via reverse proxy/LB. TLS for backend service connections.
    * **Encryption at Rest:** DB (managed service feature), File Storage (SSE). Application-level for specific fields if high-risk (future consideration).

## 7. Infrastructure Security (Strategic Overview - Collaboration with DevOps)

    * Network Security (Firewalls, SG/NACLs), OS Hardening, Container Security (minimal images, scan, non-root), Access Control (bastion hosts). Optional API Gateway.

## 8. Logging & Monitoring (Security Focus - Strategic Overview - see `monitoring_strategy.md`)

    * Audit Logging (custom service), Access Logs, SIEM integration, Alerting for suspicious activity.

## 9. Incident Response (Strategic Overview - Planning)

    * Basic plan: Preparation, Identification, Containment, Eradication, Recovery, Lessons Learned.

## 10. Compliance (Strategic Overview)

    * Identify and align with relevant data protection regulations (GDPR, CCPA, etc.).

## 11. General Setup Implementation Details (Security Components in FastAPI)

    This section details the setup of core security-enhancing components within the FastAPI application.

    ### 11.1. Library Installation (Confirm in `requirements/base.txt`)
    *   `fastapi` (core)
    *   `pydantic` (core, for input validation)
    *   `python-jose[cryptography]` (for JWT)
    *   `passlib[bcrypt]` (for password hashing)
    *   `slowapi` (for rate limiting on auth endpoints, already in API strategy)
    *   `starlette` (FastAPI is built on it, provides `MiddlewareMixin`)

    ### 11.2. CORS Configuration (`app/main.py`)
    *   Use FastAPI's `CORSMiddleware`.
        ```python
        # app/main.py
        from fastapi import FastAPI
        from fastapi.middleware.cors import CORSMiddleware
        from app.core.config import settings # Your Pydantic settings

        app = FastAPI(
            # ... other FastAPI app params ...
        )

        app.add_middleware(
            CORSMiddleware,
            allow_origins=[str(origin) for origin in settings.CORS_ALLOWED_ORIGINS], # Load from Pydantic settings
            allow_credentials=True, # If your frontend sends cookies/auth headers that need to be passed
            allow_methods=["*"],    # Or specify ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
            allow_headers=["*"],    # Or specify a list of allowed headers
            expose_headers=["Content-Disposition", "X-Request-ID"] # Example of exposing custom headers
        )
        # ... rest of app setup ...
        ```
    *   **Configuration (`app/core/config.py`):**
        `CORS_ALLOWED_ORIGINS: List[str]` (e.g., `["http://localhost:3000", "https://myfrontend.example.com"]`). This **must** be configured per environment.

    ### 11.3. Security Headers Middleware (`app/core/middleware/security_headers.py`)
    *   Create a custom Starlette middleware to add common security headers.
        ```python
        # app/core/middleware/security_headers.py
        from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseCall
        from starlette.requests import Request
        from starlette.responses import Response
        from typing import Optional

        class SecurityHeadersMiddleware(BaseHTTPMiddleware):
            async def dispatch(self, request: Request, call_next: RequestResponseCall) -> Response:
                response = await call_next(request)
                response.headers["X-Content-Type-Options"] = "nosniff"
                response.headers["X-Frame-Options"] = "DENY" # Or "SAMEORIGIN"
                # response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; object-src 'none';" # Example CSP, very restrictive
                response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains" # If site is HTTPS only
                # response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
                # response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()" # Disable features by default
                return response

        # In app/main.py:
        # from app.core.middleware.security_headers import SecurityHeadersMiddleware
        # app.add_middleware(SecurityHeadersMiddleware)
        ```
    *   *Note: `Content-Security-Policy` (CSP) can be complex to configure correctly without breaking frontend functionality. Start with a basic policy or omit it if the frontend handles its own CSP, and iterate.*

    ### 11.4. Authentication Utilities (`app/core/security.py`)
    *   This module will contain helpers for password hashing and JWT creation/decoding.
        ```python
        # app/core/security.py
        from datetime import datetime, timedelta, timezone
        from typing import Optional, Dict, Any
        from jose import JWTError, jwt
        from passlib.context import CryptContext
        from pydantic import BaseModel, ValidationError

        from app.core.config import settings

        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

        class TokenPayload(BaseModel):
            sub: str # Subject (e.g., user_id or username)
            exp: Optional[datetime] = None
            # Add other claims like roles, organization_id if embedding in token
            # org_id: Optional[int] = None

        def verify_password(plain_password: str, hashed_password: str) -> bool:
            return pwd_context.verify(plain_password, hashed_password)

        def get_password_hash(password: str) -> str:
            return pwd_context.hash(password)

        def create_access_token(subject: Union[str, Any], expires_delta: Optional[timedelta] = None) -> str:
            if expires_delta:
                expire = datetime.now(timezone.utc) + expires_delta
            else:
                expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)

            to_encode = TokenPayload(sub=str(subject), exp=expire).model_dump()
            # to_encode.update({"org_id": organization_id}) # Example of adding more claims
            encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
            return encoded_jwt

        def decode_access_token(token: str) -> Optional[TokenPayload]:
            try:
                payload_dict = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
                # Validate payload against Pydantic model to ensure structure and types
                token_data = TokenPayload(**payload_dict)
                if token_data.exp and token_data.exp < datetime.now(timezone.utc):
                    # This check is also done by jwt.decode if 'exp' is present and verify_exp=True (default)
                    # However, explicit check after Pydantic validation is fine.
                    return None # Token expired
                return token_data
            except (JWTError, ValidationError):
                return None # Invalid token (format, signature, claims, or expired)
        ```

    ### 11.5. API Key Storage (Conceptual - Models in `app/features/users/models.py` or dedicated `api_keys` feature)
    *   SQLAlchemy model for `APIKey` storing `prefix`, `hashed_key`, `user_id`, `name`, `expires_at`, `is_active`.
    *   Service functions for creating (showing full key once), validating (lookup by prefix, hash key part, check expiry/active), and revoking keys. Hashing done using a standard algorithm like SHA256.

## 12. Integration & Usage Patterns

    This section illustrates how security components are used within the application.

    ### 12.1. Protecting Endpoints with Authentication
    *   Authentication dependencies (`get_current_active_user`, `verify_api_key_dependency` from `app/core/auth_dependencies.py`) are applied to path operations.
        ```python
        # app/features/items/router.py
        # from app.core.auth_dependencies import get_current_active_user
        # from app.users.schemas import UserRead # Pydantic schema for User

        # @router.get("/my-items")
        # async def list_my_items(current_user: UserRead = Depends(get_current_active_user)):
        #     # current_user is now an authenticated user object
        #     # return await item_service.get_items_for_user(user_id=current_user.id)
        #     pass
        ```

    ### 12.2. Applying RBAC and Organization-Scoped Permissions
    *   The `require_organization_permission` dependency (from `app/core/rbac_dependencies.py`) is used, which itself relies on an authentication dependency.
        ```python
        # app/features/products/router.py
        # from app.core.rbac_dependencies import require_organization_permission

        # @router.post(
        #     "/{organization_id}/products/",
        #     dependencies=[Depends(require_organization_permission("product:create"))]
        # )
        # async def create_product_in_org(organization_id: int, product_in: ProductCreate, ...):
        #     # Access granted if dependency doesn't raise HTTPException
        #     pass
        ```
    *   The `rbac_service` (called by `require_organization_permission`) will implement the logic to check if `current_user.roles` grant `product:create` *within the context of* `organization_id`.

    ### 12.3. Input Validation with Pydantic
    *   All request bodies, query parameters, and path parameters are defined with Pydantic models or type hints in path operation function signatures. FastAPI handles the validation automatically. (Refer to `validation_strategy.md` for Pydantic examples).

    ### 12.4. Rate Limiting Auth Endpoints
    *   Apply `slowapi` decorators to sensitive endpoints like login, password reset request, etc.
        ```python
        # app/features/users/routers/auth_router.py (example)
        # from app.main import limiter # If limiter is initialized in main.py and made accessible
        # from starlette.requests import Request as StarletteRequest

        # @auth_router.post("/token/obtain")
        # @limiter.limit("5/minute") # Example: 5 attempts per minute per IP
        # async def login_for_access_token(request: StarletteRequest, ...): # request needed by limiter
        #     # ... login logic ...
        #     pass
        ```

    ### 12.5. Secure File Handling
    *   Uploads are validated (type, size).
    *   Pre-signed URLs are used for direct S3 uploads/downloads.
    *   Permissions are checked before granting access to file metadata or generating download URLs.
    *   (Refer to `file_storage_strategy.md`).

    ### 12.6. Regular Dependency Updates
    *   Utilize `pip-audit` or Dependabot/Snyk in CI to identify vulnerable dependencies.
    *   Establish a recurring task (e.g., monthly sprint task) to review and update dependencies in `requirements/*.txt` files and test thoroughly.
