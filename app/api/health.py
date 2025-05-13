from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.core.dependencies import get_db_session
from app.core.redis_client import get_redis_app_cache_client
import redis.asyncio as aioredis
from typing import Dict, Optional

router = APIRouter(tags=["health"])

@router.get("/health")
async def health_check(
    db: Optional[AsyncSession] = Depends(get_db_session),
) -> Dict[str, str]:
    """
    Health check endpoint to verify the application is running
    and its connections to critical dependencies are working.
    """
    health_status = {
        "status": "ok",
        "database": "unknown",
        "redis": "unknown"
    }
    
    # Check database connection
    if db is not None:
        try:
            # Use simple query to validate connection with text() function
            result = await db.execute(text("SELECT 1"))
            if result.scalar_one() == 1:
                health_status["database"] = "ok"
            else:
                health_status["database"] = "error"
        except Exception as e:
            health_status["database"] = f"error: {str(e)}"
            health_status["status"] = "degraded"
    else:
        health_status["database"] = "not available"
        health_status["status"] = "degraded"
    
    # Check Redis connection
    redis_client = await get_redis_app_cache_client()
    if redis_client is not None:
        try:
            if await redis_client.ping():
                health_status["redis"] = "ok"
            else:
                health_status["redis"] = "error"
                health_status["status"] = "degraded"
        except Exception as e:
            health_status["redis"] = f"error: {str(e)}"
            health_status["status"] = "degraded"
    else:
        health_status["redis"] = "not available"
        health_status["status"] = "degraded"
    
    return health_status

@router.get("/healthz/live", include_in_schema=False)
async def liveness_check() -> Dict[str, str]:
    """
    Liveness probe endpoint for Kubernetes/container orchestrators.
    Returns 200 OK as long as the application is running.
    """
    return {"status": "alive"}

@router.get("/healthz/ready", include_in_schema=False)
async def readiness_check(
    response: Response,
    db: Optional[AsyncSession] = Depends(get_db_session),
) -> Dict[str, str]:
    """
    Readiness probe endpoint for Kubernetes/container orchestrators.
    Verifies the application is ready to receive traffic by checking 
    connectivity to critical dependencies like the database and Redis.
    """
    is_ready = True
    status_details = {
        "status": "ready",
        "database": "up",
        "redis": "up"
    }
    
    # Check database connection
    if db is not None:
        try:
            result = await db.execute(text("SELECT 1"))
            if result.scalar_one() != 1:
                status_details["database"] = "down"
                is_ready = False
        except Exception:
            status_details["database"] = "down"
            is_ready = False
    else:
        status_details["database"] = "down"
        is_ready = False
    
    # Check Redis connection
    redis_client = await get_redis_app_cache_client()
    if redis_client is not None:
        try:
            if not await redis_client.ping():
                status_details["redis"] = "down"
                is_ready = False
        except Exception:
            status_details["redis"] = "down"
            is_ready = False
    else:
        status_details["redis"] = "down"
        is_ready = False
    
    # Set overall status
    if not is_ready:
        status_details["status"] = "not ready"
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    
    return status_details 