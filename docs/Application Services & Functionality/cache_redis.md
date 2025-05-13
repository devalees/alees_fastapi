# Caching Strategy (Redis with FastAPI)

## 1. Overview

- **Purpose**: To define the setup and usage strategy for Redis as the primary caching backend for the FastAPI application. Redis also serves as the message broker/result backend for Celery and supports other features like rate limiting and feature flag caching.
- **Scope**: Redis client selection, configuration, connection management, patterns for cache interaction (get, set, delete, invalidation), use cases, and implementation details for integrating Redis caching into the FastAPI application.
- **Chosen Technology**: **Redis** (Target Version: 6.x+ or latest stable), **`redis-py` (async interface: `redis.asyncio`)** Python client.

## 2. Core Requirements

- **Fast In-Memory Cache**: Provide low-latency caching for frequently accessed data.
- **Asynchronous Operations**: All cache interactions from FastAPI application code must be asynchronous.
- **Connection Pooling**: Efficiently manage Redis connections.
- **Multiple Logical Databases**: Utilize different Redis logical DBs for different purposes (caching, Celery, rate limiting, feature flags) for separation.

## 3. Configuration & Connection Management (Strategic Overview)

- **Redis Client Library**: `redis-py` (async interface).
- **Configuration (`app/core/config.py` - Pydantic Settings):**
  - `REDIS_HOST`, `REDIS_PORT`, `REDIS_PASSWORD` (optional).
  - `REDIS_MAX_CONNECTIONS` (for general cache pool).
  - Specific DB numbers: `REDIS_CACHE_DB`, `REDIS_CELERY_BROKER_DB`, `REDIS_CELERY_RESULT_DB`, `REDIS_RATE_LIMIT_DB`, `REDIS_FEATURE_FLAG_DB`.
  - Derived URL properties (e.g., `REDIS_CACHE_URL`).
- **Connection Pool & Client Instantiation (`app/core/redis_client.py`):** A module to manage Redis connection pool(s) and provide client instances.

## 4. Cache Interaction Patterns (Strategic Guidelines)

- Access via injected `aioredis.Redis` client.
- Basic async operations: `set`, `get`, `delete`, `exists`.
- Serialization/Deserialization (JSON for Pydantic models/complex types).
- Consistent Cache Key Naming Convention (e.g., `erp:{context}:{object_type}:{id}:{sub_context}`).
- Recommended: Cache Abstraction Layer/Utilities (`app/core/cache_utils.py`).
- Recommended: Async Caching Decorator for service functions.

## 5. Cache Invalidation (Strategic Guidelines)

- Explicit invalidation on CUD operations.
- Consider pattern-based deletion carefully or tag-based invalidation for advanced needs.
- Utilize TTLs for eventual consistency.

## 6. Specific Use Cases & Integration Points (Strategic Overview)

- Application Data Caching (DB queries, computed results, module settings).
- Celery Broker & Result Backend.
- Feature Flag Evaluations.
- Rate Limiting (`slowapi`).
- WebSockets Broadcast Layer (if `broadcaster` with Redis is used).

## 7. Local Development Setup (`docker-compose.yml` - Strategic Consideration)

    * Redis service definition.

## 8. Security Considerations (Strategic Consideration)

    * Password protection, network access limits, TLS/SSL.

## 9. Monitoring Considerations (Strategic Consideration)

    * Key Redis metrics.

## 10. Backup & Recovery Strategy (Strategic Consideration)

    * Cache data is ephemeral. Broker/persistent use DBs need AOF/backups.

## 11. Testing (`Pytest` - Strategic Consideration)

    * Mocking, `fakeredis[aioredis]`, or real test Redis instance.

## 12. General Setup Implementation Details

    This section details the one-time setup and core configurations for integrating Redis caching.

    ### 12.1. Library Installation
    *   Ensure `redis[hiredis]>=5.0.0,<5.1.0` (or latest stable) is present in `requirements/base.txt`. (`hiredis` is an optional C extension for faster parsing).

    ### 12.2. Pydantic Settings (`app/core/config.py`)
    *   Verify all Redis-related settings mentioned in Section 3 are defined in your `Settings` class:
        ```python
        # In Pydantic Settings class (app/core/config.py)
        REDIS_HOST: str = "localhost"
        REDIS_PORT: int = 6379
        REDIS_PASSWORD: Optional[str] = None
        REDIS_MAX_CONNECTIONS: int = 20 # For the general application cache pool

        REDIS_CACHE_DB: int = 1
        # ... other DB numbers for Celery, Rate Limiting, Feature Flags ...

        # Example property for the general cache URL (if not providing full URLs directly)
        @property
        def APP_CACHE_REDIS_URL(self) -> str:
            auth = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
            return f"redis://{auth}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_CACHE_DB}"
        ```

    ### 12.3. Redis Client Module (`app/core/redis_client.py`)
    *   Implement the connection pool and client provider for the general application cache.
        ```python
        # app/core/redis_client.py
        import redis.asyncio as aioredis
        from redis.asyncio.connection import ConnectionPool
        from app.core.config import settings # Your Pydantic settings instance
        from typing import Optional
        import logging

        logger = logging.getLogger(__name__)

        _app_cache_pool: Optional[ConnectionPool] = None
        _app_cache_client: Optional[aioredis.Redis] = None

        async def init_app_redis_pool():
            """Initializes the Redis connection pool for general application caching."""
            global _app_cache_pool, _app_cache_client
            if _app_cache_pool is None:
                try:
                    logger.info(f"Initializing Redis app cache pool for URL: {settings.APP_CACHE_REDIS_URL} (components: host={settings.REDIS_HOST}, port={settings.REDIS_PORT}, db={settings.REDIS_CACHE_DB})")
                    # Using from_url which handles parsing username/password if present in the URL
                    _app_cache_pool = ConnectionPool.from_url(
                        settings.APP_CACHE_REDIS_URL, # Use the constructed URL from settings
                        max_connections=settings.REDIS_MAX_CONNECTIONS,
                        decode_responses=True, # Automatically decode responses from bytes to str
                    )
                    _app_cache_client = aioredis.Redis(connection_pool=_app_cache_pool)
                    # Test connection
                    await _app_cache_client.ping()
                    logger.info("Successfully connected to Redis app cache pool and pinged.")
                except Exception as e:
                    logger.error(f"Failed to initialize Redis app cache pool: {e}", exc_info=True)
                    # Depending on strictness, you might re-raise or allow app to start without cache
                    _app_cache_pool = None # Ensure it's None if init fails
                    _app_cache_client = None
            return _app_cache_client

        async def get_redis_app_cache_client() -> Optional[aioredis.Redis]:
            """
            Returns a Redis client instance from the general application cache pool.
            Returns None if the pool couldn't be initialized.
            """
            if _app_cache_client is None:
                await init_app_redis_pool() # Attempt to initialize if not already
            return _app_cache_client # Could be None if init_app_redis_pool failed

        async def close_app_redis_pool():
            """Closes the general application Redis connection pool."""
            global _app_cache_pool, _app_cache_client
            if _app_cache_client:
                await _app_cache_client.close() # Close client first
                _app_cache_client = None
            if _app_cache_pool:
                await _app_cache_pool.disconnect()
                _app_cache_pool = None
            logger.info("Redis app cache pool closed.")

        # Note: Celery and other libraries like slowapi will typically manage their own
        # Redis connections using their respective configuration URLs from settings.
        # This redis_client.py is primarily for direct application caching needs.
        ```

    ### 12.4. FastAPI Application Hooks (`app/main.py`)
    *   Integrate Redis pool initialization and cleanup with the FastAPI application lifecycle.
        ```python
        # app/main.py
        # from fastapi import FastAPI
        # from app.core.redis_client import init_app_redis_pool, close_app_redis_pool
        # # ... other imports

        # app = FastAPI()

        # @app.on_event("startup")
        # async def on_startup():
        #     await init_app_redis_pool()
        #     # ... other startup tasks

        # @app.on_event("shutdown")
        # async def on_shutdown():
        #     await close_app_redis_pool()
        #     # ... other shutdown tasks
        ```

    ### 12.5. Docker Compose Service (for local development/testing)
    *   Ensure the `redis` service is defined in `docker-compose.yml`.
        ```yaml
        # docker-compose.yml
        # services:
        #   redis:
        #     image: "redis:7-alpine" # Or desired version
        #     ports:
        #       - "6379:6379"
        #     volumes:
        #       - redis_data:/data # Optional: for persistence
        #     # command: redis-server --requirepass yourlocalredispassword # If password needed
        # volumes:
        #   redis_data:
        ```
        Your local `.env` file would set `REDIS_HOST=redis` (if app is in same Docker network) or `localhost` (if accessing via mapped port), and `REDIS_PASSWORD` if configured.

## 13. Integration & Usage Patterns

    This section provides examples of how to use the Redis cache within application features.

    ### 13.1. FastAPI Dependency for Redis Client
    *   Create a dependency to inject the Redis client into path operations or services.
        ```python
        # app/core/dependencies.py
        # from fastapi import HTTPException, status
        # from app.core.redis_client import get_redis_app_cache_client
        # import redis.asyncio as aioredis
        # from typing import Optional

        # async def get_cache_client() -> aioredis.Redis:
        #     """FastAPI dependency to get an application cache Redis client."""
        #     client = await get_redis_app_cache_client()
        #     if client is None:
        #         # Decide behavior: raise error or allow app to function without cache
        #         raise HTTPException(
        #             status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        #             detail="Cache service is currently unavailable."
        #         )
        #     return client
        ```

    ### 13.2. Basic Get/Set with Serialization (Service Layer Example)
        ```python
        # app/features/products/service.py
        # import json
        # from typing import Optional
        # from . import schemas, models
        # from app.core.redis_client import get_redis_app_cache_client # Or use dependency
        # import redis.asyncio as aioredis

        # async def get_product_details_cached(product_id: int, redis_client: aioredis.Redis) -> Optional[schemas.ProductRead]:
        #     cache_key = f"erp:cache:product:{product_id}:details"
        #     cached_data_json = await redis_client.get(cache_key)

        #     if cached_data_json:
        #         return schemas.ProductRead.model_validate_json(cached_data_json)

        #     # product_orm = await get_product_from_db(product_id) # Your DB fetch logic
        #     # if not product_orm:
        #     #     return None
        #     # product_schema = schemas.ProductRead.from_orm(product_orm)

        #     # For example purposes, creating a dummy schema
        #     product_schema = schemas.ProductRead(id=product_id, name=f"Product {product_id}", sku=f"SKU{product_id}", price=10.0)

        #     await redis_client.set(cache_key, product_schema.model_dump_json(), ex=3600) # Cache for 1 hour
        #     return product_schema

        # async def clear_product_details_cache(product_id: int, redis_client: aioredis.Redis):
        #     cache_key = f"erp:cache:product:{product_id}:details"
        #     await redis_client.delete(cache_key)
        ```

    ### 13.3. Implementing Cache Utilities (`app/core/cache_utils.py`)
    *   Encapsulate common patterns like key generation and Pydantic model serialization.
        ```python
        # app/core/cache_utils.py
        # import json
        # from typing import Optional, Type, TypeVar, Any
        # from pydantic import BaseModel
        # from app.core.dependencies import get_cache_client # Assuming this is your dependency
        # import redis.asyncio as aioredis
        # from fastapi import Depends # If used within other dependencies or directly

        # T = TypeVar("T", bound=BaseModel)
        # DEFAULT_TTL = 3600 # 1 hour

        # def _generate_cache_key(prefix: str, *args: Any, **kwargs: Any) -> str:
        #     key_parts = [str(arg) for arg in args]
        #     key_parts.extend([f"{k}_{v}" for k, v in sorted(kwargs.items())])
        #     return f"erp:cache:{prefix}:{':'.join(key_parts)}"

        # async def get_pydantic_from_cache(key: str, model_type: Type[T], redis_client: aioredis.Redis) -> Optional[T]:
        #     cached_json = await redis_client.get(key)
        #     if cached_json:
        #         return model_type.model_validate_json(cached_json)
        #     return None

        # async def set_pydantic_to_cache(key: str, value: T, redis_client: aioredis.Redis, ttl: int = DEFAULT_TTL):
        #     await redis_client.set(key, value.model_dump_json(), ex=ttl)

        # async def delete_from_cache(key: str, redis_client: aioredis.Redis):
        #     await redis_client.delete(key)
        ```

    ### 13.4. Implementing an Async Caching Decorator
    *   A decorator to simplify caching function/method results.
        ```python
        # app/core/cache_utils.py (continued)
        # import functools

        # def cached_async(key_prefix: str, model_type: Optional[Type[BaseModel]] = None, ttl: int = DEFAULT_TTL):
        #     def decorator(func):
        #         @functools.wraps(func)
        #         async def wrapper(*args, **kwargs):
        #             # First arg is often 'self' or 'cls', or 'db_session'.
        #             # The actual client should be passed or available in context.
        #             # This example assumes redis_client is passed as a kwarg or available globally for simplicity.
        #             # In a real app, it should be properly injected or accessed.
        #             redis_client_from_kwargs = kwargs.get("redis_client")
        #             if not isinstance(redis_client_from_kwargs, aioredis.Redis):
        #                  # Fallback or raise error: ideally get it from a dependency context
        #                  # This is a simplified example; proper DI is needed for the client.
        #                  # For instance, the decorated function itself might need to accept redis_client
        #                  # or use a class that has it.
        #                  # For now, let's assume it's magically available or the decorated function
        #                  # itself will acquire it if it's a method of a class that has it.
        #                  # A better approach for decorators used on service methods:
        #                  # The decorator is applied to a method of a class that has self.redis_client.
        #                  # Or the decorator itself accepts the redis_client as an argument.
        #                 pass # Placeholder for real client acquisition

        #             # Simplified key generation; exclude 'self', 'cls', 'db', 'redis_client' from args for key
        #             cache_key_args = [a for a in args if not (hasattr(a, '__class__') and (type(a).__name__ == 'ServiceClass' or isinstance(a, AsyncSession)))]

        #             cache_key = _generate_cache_key(f"{key_prefix}:{func.__name__}", *cache_key_args, **kwargs)
        #
        #             # This is where you'd get the redis_client, e.g., from args[0] if it's self.redis_client
        #             # For this example, let's assume a global or passed-in redis_client
        #             # For a more robust decorator, you'd pass the client instance to the decorator factory
        #             # or ensure the decorated method's class has a `self.redis_client`.
        #             # This example is highly conceptual for brevity.
        #
        #             # Assume redis_client is available (e.g. from kwargs or self)
        #             # if 'redis_client' not in kwargs: raise ValueError("redis_client missing")
        #             # temp_redis_client = kwargs['redis_client'] # Example
        #
        #             # For a realistic decorator, it would likely be part of a class or expect client via DI.
        #             # We'll skip actual Redis calls here as client injection to decorator is complex for this example.
        #             # The core logic:
        #             # cached_value = await get_from_cache(cache_key, model_type, temp_redis_client)
        #             # if cached_value: return cached_value
        #             # result = await func(*args, **kwargs)
        #             # await set_to_cache(cache_key, result, model_type, temp_redis_client, ttl)
        #             # return result

        #             # This is just a placeholder for the actual logic
        #             print(f"CACHE_DECORATOR: Would check/use cache key: {cache_key}")
        #             return await func(*args, **kwargs) # Call original function
        #         return wrapper
        #     return decorator

        # @cached_async(key_prefix="user_data", model_type=UserSchema, ttl=600)
        # async def get_user_details(user_id: int, db: AsyncSession, redis_client: aioredis.Redis):
        #    # ... fetch from db ...
        #    pass
        ```
        *The decorator implementation needs careful handling of `*args` and `**kwargs` for cache key generation and passing the `redis_client` instance.*

    ### 13.5. Cache Invalidation Example (in a Service)
        ```python
        # app/features/products/service.py
        # async def update_product_service(product_id: int, update_data: schemas.ProductUpdate,
        #                                 db: AsyncSession, redis_client: aioredis.Redis):
        #     # ... update product_orm in db ...
        #     # await db.commit()
        #     # await db.refresh(product_orm)

        #     # Invalidate cache
        #     cache_key = f"erp:cache:product:{product_id}:details" # Key used by get_product_details_cached
        #     await redis_client.delete(cache_key)
        #     # Invalidate list caches if any
        #     # await redis_client.delete_keys_by_pattern("erp:cache:product:list:*") # If using pattern based list keys

        #     return schemas.ProductRead.from_orm(product_orm)
        ```
