# Validation Strategy (FastAPI Edition)

## 1. Overview

    * Purpose: To define the standard approach for implementing data validation across the FastAPI-based ERP system, ensuring data integrity, enforcing business rules, and providing clear, structured feedback.
    * Scope: Covers validation at the API input layer (Pydantic), service/business logic layer, and database constraint level.
    * Goal: Robust, maintainable, type-safe, and consistently applied validation, with clear error reporting as per `api_strategy.md`.

## 2. Core Principles

    * Validate Early (Pydantic for API input).
    * Leverage Pydantic & Type Hints extensively.
    * Clarity of Errors (Standard API error format).
    * DRY (Reusable Pydantic validators/models).
    * Separation of Concerns:
        * Pydantic: Format, type, presence, basic constraints.
        * Service Layer/Pydantic Custom Validators: Complex business rules, cross-field validation.
        * Database Constraints: Final integrity safeguard.

## 3. Validation Layers & Techniques (Strategic Overview - already detailed)

    * **3.1. Pydantic Model Validation (Primary):** FastAPI auto-validates request bodies, query/path params against Pydantic models (Type hints, `Field`, `@validator`, `@model_validator`).
    * **3.2. Service Layer / Business Logic Validation:** For rules needing DB lookups or complex context. Raise custom exceptions.
    * **3.3. Database Level Constraints (PostgreSQL):** `NOT NULL`, `UNIQUE`, `FOREIGN KEY`, `CHECK` constraints via SQLAlchemy.

## 4. Strategy Summary (Strategic Overview - already detailed)

    * Pydantic first, then Service Layer, then DB constraints. Consistent error reporting.

## 5. Integration with Other Systems (Strategic Overview - already detailed)

    * RBAC (checks before/alongside validation).
    * Workflow System (state transition validation).
    * Custom Fields (dynamic validation against definitions).

## 6. Testing (Pytest - Strategic Overview)

    * Unit tests for Pydantic models/validators. API tests (via `TestClient`) for endpoint validation behavior. Service layer tests for business rule validation.

## 7. General Setup Implementation Details

    This section details the setup for custom validation error handling to align with the API's standard error format.

    ### 7.1. Pydantic Library
    *   `pydantic>=2.0.0,<3.0.0` is a core dependency of FastAPI and should be in `requirements/base.txt`.
    *   Optional: `email-validator>=2.0.0,<2.1.0` if using `EmailStr` for robust email validation (add to `requirements/base.txt`).

    ### 7.2. Standard Error Response Schemas (`app/core/schemas/errors.py`)
    *   Define Pydantic models for the standard API error response structure, as specified in `api_strategy.md`.
        ```python
        # app/core/schemas/errors.py
        from pydantic import BaseModel, Field
        from typing import List, Dict, Any, Optional, Tuple

        class ErrorSource(BaseModel):
            pointer: Optional[str] = None # JSON Pointer to the field in request body
            parameter: Optional[str] = None # Name of query/path parameter

        class ErrorMeta(BaseModel):
            field_errors: Optional[Dict[str, List[str]]] = None # Detailed Pydantic field errors
            allowed_methods: Optional[List[str]] = None # For 405 errors
            # Add other meta fields as needed, e.g., for custom error codes

        class ErrorDetail(BaseModel):
            status: str # HTTP status code as a string
            code: str   # Application-specific error code
            detail: str # Human-readable general explanation
            source: Optional[ErrorSource] = None
            meta: Optional[ErrorMeta] = None

        class ErrorResponse(BaseModel):
            errors: List[ErrorDetail]
        ```

    ### 7.3. Custom Exception Handler for `RequestValidationError` (`app/main.py`)
    *   FastAPI raises `RequestValidationError` when Pydantic model validation fails for request data. Override the default handler to format these errors according to `ErrorResponse`.
        ```python
        # app/main.py (add or ensure this handler is present)
        from fastapi import FastAPI, Request, status, HTTPException
        from fastapi.responses import JSONResponse
        from fastapi.exceptions import RequestValidationError
        from app.core.schemas.errors import ErrorResponse, ErrorDetail, ErrorSource, ErrorMeta # Import your error schemas

        # app = FastAPI(...) # Your app instance

        @app.exception_handler(RequestValidationError)
        async def pydantic_validation_exception_handler(request: Request, exc: RequestValidationError):
            """
            Custom handler for Pydantic's RequestValidationError to fit the standard error format.
            """
            field_errors: Dict[str, List[str]] = {}
            # exc.errors() provides a list of dicts, each detailing an error
            # [{'type': '...', 'loc': ('body', 'field_name'), 'msg': '...', 'input': ...}]
            for error in exc.errors():
                # Construct a more user-friendly field path if nested
                # loc often contains ('body', 'field_name') or ('query', 'param_name')
                # We want to extract the actual field/param name path
                location_tuple = error.get("loc", ())
                if len(location_tuple) > 1:
                    # Skip the first element if it's 'body', 'query', 'path' for a cleaner field key
                    field_key_parts = [str(loc_part) for loc_part in location_tuple[1:]]
                    field_key = ".".join(field_key_parts) if field_key_parts else "general"
                elif len(location_tuple) == 1:
                    field_key = str(location_tuple[0])
                else:
                    field_key = "unknown_field"

                if field_key not in field_errors:
                    field_errors[field_key] = []
                field_errors[field_key].append(error["msg"])

            # Determine the source pointer (optional, can point to the first error)
            first_error_loc = exc.errors()[0].get("loc") if exc.errors() else None
            source_pointer = None
            source_parameter = None
            if first_error_loc:
                if first_error_loc[0] == 'body':
                    source_pointer = "/" + "/".join(str(loc) for loc in first_error_loc)
                elif first_error_loc[0] in ('query', 'path'):
                    source_parameter = str(first_error_loc[1]) if len(first_error_loc) > 1 else str(first_error_loc[0])


            error_detail_obj = ErrorDetail(
                status=str(status.HTTP_422_UNPROCESSABLE_ENTITY), # Or 400
                code="validation_error",
                detail="One or more validation errors occurred. Please check the 'field_errors' for details.",
                source=ErrorSource(pointer=source_pointer, parameter=source_parameter) if source_pointer or source_parameter else None,
                meta=ErrorMeta(field_errors=field_errors)
            )
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                content=ErrorResponse(errors=[error_detail_obj]).model_dump(exclude_none=True),
            )
        ```
        *This handler needs to be registered with the FastAPI app instance in `app/main.py`.*

    ### 7.4. Custom Application Exception Definitions (e.g., `app/core/exceptions.py`)
    *   Define custom exceptions for service layer validation failures. These can inherit from `HTTPException` to carry status codes and details, or be standard Python exceptions handled by specific handlers.
        ```python
        # app/core/exceptions.py
        # from fastapi import HTTPException, status

        # class NotFoundError(HTTPException):
        #     def __init__(self, detail: str = "Resource not found", item_id: Any = None):
        #         super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)
        #         self.error_code = "not_found" # Custom code for your ErrorResponse
        #         self.item_id = item_id # Example of adding more context

        # class InvalidOperationError(HTTPException):
        #     def __init__(self, detail: str = "Operation not allowed", error_code: str = "invalid_operation"):
        #         super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)
        #         self.error_code = error_code

        # class ConflictError(HTTPException):
        #     def __init__(self, detail: str = "Resource conflict", error_code: str = "conflict_error"):
        #         super().__init__(status_code=status.HTTP_409_CONFLICT, detail=detail)
        #         self.error_code = error_code
        ```
    *   Ensure these custom exceptions (or a base `HTTPException` handler) are also mapped to your standard `ErrorResponse` format in `app/main.py` (as shown in the API strategy's general setup for `custom_http_exception_handler`).

## 8. Integration & Usage Patterns

    This section provides examples of how Pydantic and service-level validation are used.

    ### 8.1. Defining Pydantic Request Models with Validation
    *   Located in `app/features/<feature_name>/schemas.py`.
        ```python
        # app/features/items/schemas.py
        from pydantic import BaseModel, Field, validator, model_validator, EmailStr
        from typing import Optional, List
        from datetime import date

        class ItemCreate(BaseModel):
            name: str = Field(..., min_length=3, max_length=50, description="Name of the item")
            description: Optional[str] = Field(None, max_length=255)
            price: float = Field(..., gt=0, le=10000.00, description="Price must be positive and not exceed 10000")
            tags: Optional[List[str]] = Field(default_factory=list, max_items=5)
            start_date: Optional[date] = None
            end_date: Optional[date] = None

            # Field-specific validator
            @validator('name')
            def name_must_be_alphanumeric(cls, v: str) -> str:
                if not v.replace(' ', '').isalnum(): # Allow spaces
                    raise ValueError('Name must be alphanumeric')
                return v.title()

            # Model-level validator (cross-field)
            @model_validator(mode='after')
            def check_dates_consistency(self) -> 'ItemCreate':
                if self.start_date and self.end_date and self.start_date > self.end_date:
                    # Pydantic v2: you can raise a list of errors for specific fields or a general ValueError
                    # For specific field errors to be caught easily by the handler:
                    # raise PydanticCustomError('date_error', 'End date must be after start date.') - needs error type definition
                    # Simpler: just raise ValueError, which Pydantic wraps.
                    raise ValueError('End date cannot be before start date.')
                return self
        ```

    ### 8.2. Using Pydantic Models in Path Operations
    *   FastAPI automatically validates against these schemas.
        ```python
        # app/features/items/router.py
        # from . import schemas, services
        # from app.core.dependencies import get_db_session, ...

        # @router.post("/", response_model=schemas.ItemRead, status_code=status.HTTP_201_CREATED)
        # async def create_item(
        #     item_in: schemas.ItemCreate, # FastAPI validates this using ItemCreate schema
        #     db: AsyncSession = Depends(get_db_session)
        # ):
        #     # If validation passes, item_in is a valid ItemCreate instance
        #     # return await services.item_service.create(db=db, obj_in=item_in)
        #     pass
        ```

    ### 8.3. Service Layer Validation Example
        ```python
        # app/features/items/services/item_service.py
        # from app.core.exceptions import InvalidOperationError, NotFoundError
        # from sqlalchemy.exc import IntegrityError # For DB constraint violations

        # async def update_item_status(db: AsyncSession, item_id: int, new_status: str):
        #     item = await get_item_by_id(db, item_id) # Assume this service func exists
        #     if not item:
        #         raise NotFoundError(detail=f"Item with ID {item_id} not found.")

        #     if item.status == "archived" and new_status != "unarchived":
        #         raise InvalidOperationError(
        #             detail="Cannot change status of an archived item unless unarchiving.",
        #             error_code="item_archived_status_change_forbidden" # Custom app error code
        #         )
        #
        #     # Check against a (hypothetical) state machine
        #     # if not item_state_machine.can_transition(item.status, new_status):
        #     #     raise InvalidOperationError(detail=f"Cannot transition item from {item.status} to {new_status}")
        #
        #     item.status = new_status
        #     db.add(item)
        #     # await db.flush() # Commit handled by dependency
        #     return item
        ```

    ### 8.4. Database Constraint Error Handling (Example)
    *   As shown in `database_strategy_postgresql.md` (Section 10.4), catch `sqlalchemy.exc.IntegrityError` in services and convert to appropriate `HTTPException` (e.g., `409 Conflict`). This `HTTPException` will then be formatted by the `custom_http_exception_handler` in `app/main.py`.

    ### 8.5. Validating Custom Fields
    *   If an entity (e.g., `Product`) has a `custom_fields: Dict[str, Any]` Pydantic field:
        1.  In a Pydantic `@model_validator` for the entity's schema, or in the service layer:
        2.  Fetch the `CustomFieldDefinition`s applicable to this entity type/instance.
        3.  Iterate through the provided `custom_fields` data.
        4.  For each custom field value, validate it against its definition (type, required, regex, choices, etc.).
        5.  Collect any validation errors and raise an appropriate `HTTPException` or add to Pydantic validation errors.
