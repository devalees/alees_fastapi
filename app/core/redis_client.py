import redis.asyncio as aioredis
from redis.asyncio.connection import ConnectionPool
from app.core.config import settings  # Your Pydantic settings instance
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
            logger.info(f"Initializing Redis app cache pool for URL: {settings.REDIS_CACHE_URL} (components: host={settings.REDIS_HOST}, port={settings.REDIS_PORT}, db={settings.REDIS_CACHE_DB})")
            # Using from_url which handles parsing username/password if present in the URL
            _app_cache_pool = ConnectionPool.from_url(
                settings.REDIS_CACHE_URL,  # Use the constructed URL from settings
                max_connections=settings.REDIS_MAX_CONNECTIONS if hasattr(settings, 'REDIS_MAX_CONNECTIONS') else 10,
                decode_responses=True,  # Automatically decode responses from bytes to str
            )
            _app_cache_client = aioredis.Redis(connection_pool=_app_cache_pool)
            # Test connection
            await _app_cache_client.ping()
            logger.info("Successfully connected to Redis app cache pool and pinged.")
        except Exception as e:
            logger.error(f"Failed to initialize Redis app cache pool: {e}", exc_info=True)
            # Depending on strictness, you might re-raise or allow app to start without cache
            _app_cache_pool = None  # Ensure it's None if init fails
            _app_cache_client = None
    return _app_cache_client

async def get_redis_app_cache_client() -> Optional[aioredis.Redis]:
    """
    Returns a Redis client instance from the general application cache pool.
    Returns None if the pool couldn't be initialized.
    """
    if _app_cache_client is None:
        await init_app_redis_pool()  # Attempt to initialize if not already
    return _app_cache_client  # Could be None if init_app_redis_pool failed

async def close_app_redis_pool():
    """Closes the general application Redis connection pool."""
    global _app_cache_pool, _app_cache_client
    if _app_cache_client:
        await _app_cache_client.close()  # Close client first
        _app_cache_client = None
    if _app_cache_pool:
        await _app_cache_pool.disconnect()
        _app_cache_pool = None
    logger.info("Redis app cache pool closed.") 