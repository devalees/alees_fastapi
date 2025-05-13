# Feature Flags Strategy (FastAPI Edition)

## 1. Overview

    * Purpose: To define the strategy for implementing and managing feature flags within the FastAPI-based ERP system, allowing for dynamic control over feature availability.
    * Scope: Covers data model, service logic for evaluation, caching, management APIs, and usage patterns.
    * Chosen Approach: A custom solution using PostgreSQL (via SQLAlchemy) for storing flag definitions/conditions, and Redis for caching evaluated flag states.

## 2. Core Principles

    * Centralized Management (via API), Dynamic Evaluation (based on context like user/org), Performance (heavy caching), Flexibility (multiple condition types), Clear Usage (FastAPI dependency).

## 3. Data Models (Strategic Overview - `app/features/feature_flags/models.py`)

    * `FeatureFlag` Model: `name` (PK), `description`, `is_globally_active`, timestamps, relationship to conditions.
    * `FeatureFlagCondition` Model: `id` (PK), `flag_name` (FK), `condition_type` (e.g., "USER_ID", "ORGANIZATION_ID", "PERCENTAGE_USER_ID", "ENV_VARIABLE_BOOLEAN"), `condition_value`, `enables_flag_when_met`.

## 4. Service Layer (Strategic Overview - `app/features/feature_flags/service.py`)

    * `is_feature_active(flag_name, user, organization, **context_kwargs)`: Core evaluation logic. Checks cache, then DB, evaluates global state and conditions, caches result.

## 5. Caching Strategy (Strategic Overview - Redis)

    * Cache evaluated flag states for specific contexts (user/org). Short to moderate TTL. Invalidation on flag/condition changes.

## 6. Management API (Strategic Overview - `app/features/feature_flags/router.py`)

    * Admin-only CRUD API endpoints for `FeatureFlag` and `FeatureFlagCondition`.

## 7. Usage in FastAPI Application (Strategic Overview)

    * FastAPI dependency `check_feature(flag_name)` to easily gate features or modify behavior in path operations.

## 8. General Setup Implementation Details

    This section details the foundational setup for the custom feature flag system.

    ### 8.1. Library Installation
    *   No new direct libraries are strictly required beyond what's used for the main application (SQLAlchemy, Pydantic, `redis-py`).
    *   Optionally, for percentage rollouts, a hashing library if not using Python's built-in `hash()` or `hashlib` directly (e.g., `mmh3` for MurmurHash3 if specific distribution properties are desired, though `hashlib.sha1` or `md5` on a stable ID then modulo is common). We'll assume `hashlib` initially.

    ### 8.2. Pydantic Settings (`app/core/config.py`)
    *   Add settings related to feature flag caching:
        ```python
        # In Settings class (app/core/config.py)
        # ...
        # REDIS_HOST, REDIS_PORT, REDIS_PASSWORD are already defined
        # REDIS_FEATURE_FLAG_DB: int = 3 # Example DB number for feature flag cache

        FEATURE_FLAG_CACHE_TTL_SECONDS: int = 60 # Default TTL for cached flag evaluations
        # ...

        # @property
        # def REDIS_FEATURE_FLAG_URL(self) -> str:
        #     auth = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
        #     return f"redis://{auth}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_FEATURE_FLAG_DB}"
        ```
        *Note: The feature flag service will use the general `redis-py` client (`get_redis_app_cache_client` but will select the `REDIS_FEATURE_FLAG_DB` when making calls, or you can create a dedicated client/pool for it if preferred for isolation).*

    ### 8.3. SQLAlchemy Models (`app/features/feature_flags/models.py`)
    *   Implement the `FeatureFlag` and `FeatureFlagCondition` SQLAlchemy models as described in Section 3.
        ```python
        # app/features/feature_flags/models.py
        from sqlalchemy import Column, String, Text, Boolean, DateTime, ForeignKey, Integer, func
        from sqlalchemy.orm import relationship, Mapped, mapped_column
        from app.core.db import Base # Your SQLAlchemy Base
        from typing import List, Optional
        from datetime import datetime

        class FeatureFlag(Base):
            __tablename__ = "feature_flags"

            name: Mapped[str] = mapped_column(String(100), primary_key=True,
                                            comment="Programmatic name, e.g., 'new_reporting_module'")
            description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
            is_globally_active: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
            created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
            updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

            conditions: Mapped[List["FeatureFlagCondition"]] = relationship(
                back_populates="flag", cascade="all, delete-orphan", lazy="selectin",
                order_by="FeatureFlagCondition.id" # Optional: ensure consistent condition order
            )

        class FeatureFlagCondition(Base):
            __tablename__ = "feature_flag_conditions"

            id: Mapped[int] = mapped_column(primary_key=True)
            flag_name: Mapped[str] = mapped_column(ForeignKey("feature_flags.name", ondelete="CASCADE"), nullable=False, index=True)
            flag: Mapped["FeatureFlag"] = relationship(back_populates="conditions")

            condition_type: Mapped[str] = mapped_column(String(50), nullable=False,
                                                        comment="USER_ID, ORGANIZATION_ID, PERCENTAGE_USER_ID, ENV_VARIABLE_BOOLEAN")
            condition_value: Mapped[str] = mapped_column(String(255), nullable=False)
            enables_flag_when_met: Mapped[bool] = mapped_column(Boolean, default=True)
            # Add a priority field if complex precedence is needed beyond global_active + condition type
            # priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
        ```

    ### 8.4. Alembic Migration for Feature Flag Tables
    *   After defining the models, generate and apply an Alembic migration:
        ```bash
        docker-compose run --rm api alembic revision --autogenerate -m "create_feature_flags_tables"
        # Review the generated script
        docker-compose run --rm api alembic upgrade head
        ```

    ### 8.5. Core Service Logic Stub (`app/features/feature_flags/service.py`)
    *   Outline the structure for the `FeatureFlagService` or standalone service functions.
        ```python
        # app/features/feature_flags/service.py
        import hashlib
        import os
        from typing import Optional, Any, Dict, List
        from sqlalchemy.ext.asyncio import AsyncSession
        from sqlalchemy.future import select
        from sqlalchemy.orm import selectinload
        import redis.asyncio as aioredis

        from app.core.config import settings
        from .models import FeatureFlag, FeatureFlagCondition
        # from app.users.schemas import UserRead as UserSchema # Assuming a User schema
        # from app.organization.schemas import OrganizationRead as OrgSchema # Assuming an Org schema

        # Placeholder for actual User/Org schemas for type hinting
        class UserSchema: id: Any; # Replace with actual
        class OrgSchema: id: Any; # Replace with actual

        async def _get_flag_from_db(db: AsyncSession, flag_name: str) -> Optional[FeatureFlag]:
            stmt = select(FeatureFlag).where(FeatureFlag.name == flag_name).options(selectinload(FeatureFlag.conditions))
            result = await db.execute(stmt)
            return result.scalar_one_or_none()

        def _evaluate_percentage_condition(condition_value_str: str, context_identifier: Any) -> bool:
            if context_identifier is None: return False
            try:
                percentage = int(condition_value_str)
                if not (0 <= percentage <= 100): return False

                # Consistent hash of the identifier (e.g., user_id)
                hasher = hashlib.md5() # Or sha1
                hasher.update(str(context_identifier).encode('utf-8'))
                hash_int = int(hasher.hexdigest(), 16)
                return (hash_int % 100) < percentage
            except ValueError:
                return False # Invalid percentage value

        async def is_feature_active(
            db: AsyncSession,
            redis_client: aioredis.Redis, # Ensure this uses the correct DB for feature flags
            flag_name: str,
            user: Optional[UserSchema] = None,
            organization: Optional[OrgSchema] = None,
            **context_kwargs: Any
        ) -> bool:
            # 1. Construct Cache Key
            user_id_part = f"user:{user.id}" if user else "user:none"
            org_id_part = f"org:{organization.id}" if organization else "org:none"
            # Add other stable context_kwargs to key if they influence conditions
            cache_key = f"erp:featureflag:eval:{flag_name}:{user_id_part}:{org_id_part}"

            # 2. Check Redis Cache
            # Ensure redis_client is configured for settings.REDIS_FEATURE_FLAG_DB
            # This might involve selecting the DB if using a general client, or having a dedicated client.
            # For simplicity, assuming client is already for the correct DB or handles selection.
            try:
                cached_value_str = await redis_client.get(cache_key)
                if cached_value_str is not None:
                    return cached_value_str == "1" # "1" for True, "0" for False
            except Exception as e: # Log Redis error and proceed to DB
                # logger.error(f"Redis cache get error for flag {flag_name}: {e}")
                pass

            # 3. If Cache Miss: Fetch from DB & Evaluate
            flag_definition = await _get_flag_from_db(db, flag_name)

            if not flag_definition:
                # logger.warning(f"Feature flag '{flag_name}' not found in database.")
                return False # Default for undefined flags

            evaluated_state = flag_definition.is_globally_active
            # More sophisticated: if globally_active=True, check disabling conditions.
            # if globally_active=False, check enabling conditions.

            # Simplified evaluation: any matching enabling condition can override global false,
            # any matching disabling condition can override global true.
            # Disabling conditions could take precedence.
            # This needs a clear rule: e.g., "One enabling condition met? -> True, unless a disabling condition is also met".
            # Or "Global state unless a condition explicitly flips it".

            # Let's assume: if is_globally_active = True, it's ON unless a condition disables it.
            # If is_globally_active = False, it's OFF unless a condition enables it.

            final_decision = flag_definition.is_globally_active

            for condition in flag_definition.conditions:
                condition_met = False
                if condition.condition_type == "USER_ID" and user:
                    condition_met = str(user.id) == condition.condition_value
                elif condition.condition_type == "ORGANIZATION_ID" and organization:
                    condition_met = str(organization.id) == condition.condition_value
                elif condition.condition_type == "PERCENTAGE_USER_ID" and user: # Assumes rollout by user.id
                    condition_met = _evaluate_percentage_condition(condition.condition_value, user.id)
                elif condition.condition_type == "ENV_VARIABLE_BOOLEAN":
                    condition_met = os.environ.get(condition.condition_value, 'false').lower() in ('true', '1', 'yes')
                # Add more condition types here...

                if condition_met:
                    if condition.enables_flag_when_met:
                        final_decision = True # An enabling condition made it true
                        # Depending on logic, might break here or continue to see if a disabling one overrides
                    else: # This is a disabling condition
                        final_decision = False
                        break # A disabling condition met, short-circuit to False

            # 4. Store in Redis Cache
            try:
                await redis_client.set(cache_key, "1" if final_decision else "0", ex=settings.FEATURE_FLAG_CACHE_TTL_SECONDS)
            except Exception as e: # Log Redis error
                # logger.error(f"Redis cache set error for flag {flag_name}: {e}")
                pass

            return final_decision

        async def invalidate_flag_cache(redis_client: aioredis.Redis, flag_name: str):
            """Invalidates all cached evaluations for a given flag name."""
            # This is a simple pattern-based delete. For high-traffic Redis, scan is better.
            # Keys might be like: erp:featureflag:eval:my_flag_name:user:123:org:456
            pattern = f"erp:featureflag:eval:{flag_name}:*"
            # async for key in redis_client.scan_iter(match=pattern):
            #    await redis_client.delete(key)
            # Or, if number of keys is manageable and pattern is simple enough for `keys`:
            keys_to_delete = await redis_client.keys(pattern)
            if keys_to_delete:
                await redis_client.delete(*keys_to_delete)
        ```

    ### 8.6. Management API Router Stub (`app/features/feature_flags/router.py`)
    *   Define the APIRouter and outline CRUD endpoints. Services will handle DB interaction and cache invalidation.
        ```python
        # app/features/feature_flags/router.py
        # from fastapi import APIRouter, Depends, HTTPException, status
        # from typing import List
        # from . import schemas, service, models # Pydantic schemas, service functions, ORM models
        # from app.core.db import AsyncSession, get_db_session
        # from app.core.redis_client import get_redis_app_cache_client # Or a dedicated FF redis client
        # import redis.asyncio as aioredis
        # # from app.core.auth_dependencies import get_current_admin_user # Needs admin auth

        # router = APIRouter(prefix="/feature-flags", tags=["Admin - Feature Flags"]) # Admin-only

        # @router.post("/", response_model=schemas.FeatureFlagRead, status_code=status.HTTP_201_CREATED)
        # async def create_feature_flag(flag_in: schemas.FeatureFlagCreate, db: AsyncSession = Depends(get_db_session) #, admin: User = Depends(get_current_admin_user)
        # ):
        #     # return await service.create_flag(db=db, flag_in=flag_in)
        #     pass

        # @router.get("/{flag_name}/", response_model=schemas.FeatureFlagRead)
        # async def read_feature_flag(flag_name: str, db: AsyncSession = Depends(get_db_session)):
        #     # db_flag = await service.get_flag_details(db=db, flag_name=flag_name)
        #     # if not db_flag: raise HTTPException(status_code=404, detail="Flag not found")
        #     # return db_flag
        #     pass

        # # ... Other CRUD endpoints for flags and conditions ...
        # # PUT, DELETE for flags
        # # POST, PUT, DELETE for /feature-flags/{flag_name}/conditions/ and conditions/{condition_id}
        # # These endpoints, when updating/deleting, MUST call service.invalidate_flag_cache()
        ```

## 9. Integration & Usage Patterns

    This section illustrates how to use the feature flag system.

    ### 9.1. FastAPI Dependency for Checking Flags (`app/features/feature_flags/dependencies.py`)
        ```python
        # app/features/feature_flags/dependencies.py
        from fastapi import Depends, HTTPException, status
        from sqlalchemy.ext.asyncio import AsyncSession
        import redis.asyncio as aioredis
        from typing import Optional

        from app.core.db import get_db_session
        from app.core.redis_client import get_redis_app_cache_client # Using general cache client, ensure DB is selected
        # from app.core.auth_dependencies import get_optional_current_user # Example: returns User or None
        # from app.core.organization_context import get_optional_current_organization # Example
        from .service import is_feature_active
        # from app.users.schemas import UserRead as UserSchema # Placeholder
        # from app.organization.schemas import OrganizationRead as OrgSchema # Placeholder

        # Placeholder for actual User/Org schemas
        class UserSchema: id: Any;
        class OrgSchema: id: Any;

        def check_feature(flag_name: str, default_if_error: bool = False):
            """
            FastAPI dependency to check if a feature flag is active.
            If default_if_error is True, it returns False on any evaluation error.
            """
            async def _dependency_evaluator(
                db: AsyncSession = Depends(get_db_session),
                # Ensure this redis client is configured for settings.REDIS_FEATURE_FLAG_DB
                # or the service.is_feature_active handles DB selection.
                redis: aioredis.Redis = Depends(get_redis_app_cache_client),
                # user: Optional[UserSchema] = Depends(get_optional_current_user),
                # organization: Optional[OrgSchema] = Depends(get_optional_current_organization)
                # For simplicity, omitting user/org context from dependency signature here,
                # but they would be passed to is_feature_active if defined and available.
                # Realistically, you'd pass user/org if your flags depend on them.
            ) -> bool:
                current_user: Optional[UserSchema] = None # Replace with actual user from auth
                current_org: Optional[OrgSchema] = None   # Replace with actual org

                try:
                    if redis is None: # Redis client failed to initialize
                        # logger.warning(f"Feature flag '{flag_name}' check: Redis unavailable, returning default_if_error.")
                        return default_if_error

                    return await is_feature_active(
                        db=db, redis_client=redis, flag_name=flag_name,
                        user=current_user, organization=current_org
                        # **request_specific_context_kwargs if any
                    )
                except Exception as e:
                    # logger.error(f"Error evaluating feature flag '{flag_name}': {e}", exc_info=True)
                    return default_if_error # Fallback on any evaluation error
            return _dependency_evaluator
        ```

    ### 9.2. Using the Dependency in Path Operations
        ```python
        # app/features/dashboards/router.py
        # from fastapi import APIRouter, Depends
        # from app.features.feature_flags.dependencies import check_feature

        # router = APIRouter(prefix="/dashboards", tags=["Dashboards"])

        # @router.get("/summary")
        # async def get_dashboard_summary(
        #     use_advanced_widgets: bool = Depends(check_feature("advanced_dashboard_widgets"))
        # ):
        #     if use_advanced_widgets:
        #         # return await dashboard_service.get_summary_with_advanced_widgets()
        #         return {"data": "Advanced dashboard summary!", "widgets_active": True}
        #     else:
        #         # return await dashboard_service.get_standard_summary()
        #         return {"data": "Standard dashboard summary.", "widgets_active": False}

        # Example: Gating an entire endpoint (less common than conditional logic within)
        # @router.get("/experimental-report", dependencies=[Depends(check_feature("experimental_reports_enabled"))])
        # async def get_experimental_report():
        #     # This endpoint will only be accessible if the flag is true.
        #     # If check_feature returns False, it would need to raise HTTPException to block.
        #     # The current check_feature returns bool, so this pattern needs adjustment
        #     # if you want to block access. A different dependency would be needed:
        #     # async def require_feature_flag(is_active: bool = Depends(check_feature(...))):
        #     #    if not is_active: raise HTTPException(404, "Feature not available")
        #     return {"report": "This is an experimental report."}
        ```

    ### 9.3. Using the Service Directly in Other Services
    *   The `is_feature_active` service can also be called directly from other service layers if decisions need to be made outside of an API request context (e.g., in a Celery task), ensuring DB and Redis clients are passed appropriately.

    ### 9.4. Admin UI/Tooling for Managing Flags
    *   The API endpoints defined in `app/features/feature_flags/router.py` will be used by an administrative frontend (or CLI tool) to manage flag definitions and conditions.


