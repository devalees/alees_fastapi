from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db import AsyncSessionFactory  # Import your session factory
import logging

logger = logging.getLogger(__name__)

async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that provides a SQLAlchemy AsyncSession.
    Manages the session lifecycle per request (commit/rollback/close).
    """
    if AsyncSessionFactory is None:
        logger.error("AsyncSessionFactory is not initialized. Database unavailable.")
        # This could raise an HTTPException(503) or let the app try and fail if services use it
        # For now, let's allow it to yield None and services must handle it
        yield None  # Or raise an error immediately
        return

    async with AsyncSessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            logger.error(f"Database session rollback due to exception: {e}", exc_info=True)
            await session.rollback()
            raise  # Re-raise the exception to be handled by FastAPI error handlers
        finally:
            # The session is automatically closed by the `async with AsyncSessionFactory()` context manager
            pass 