from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

# Create an asynchronous engine instance
# The URL should be the fully qualified database URL from settings
# echo=settings.DB_ECHO_SQL can be useful for development to see generated SQL
try:
    async_engine = create_async_engine(
        settings.DATABASE_URL.render_as_string(hide_password=False)
            if hasattr(settings.DATABASE_URL, 'render_as_string')
            else str(settings.DATABASE_URL),
        echo=settings.DB_ECHO_SQL,
        pool_pre_ping=True,  # Good practice to check connections before use
        # Adjust pool size based on expected concurrency and DB limits
        pool_size=settings.DB_POOL_SIZE, # Example, make configurable
        max_overflow=settings.DB_MAX_OVERFLOW, # Example
    )
except Exception as e:
    logger.error(f"Failed to create SQLAlchemy async engine: {e}", exc_info=True)
    # Depending on how critical DB is at import time, you might raise or handle
    async_engine = None


# Create an asynchronous session factory
# autocommit=False and autoflush=False are standard for web applications
# to allow for explicit transaction control per request.
AsyncSessionFactory = async_sessionmaker(
    bind=async_engine if async_engine else None, # Bind only if engine was created
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False # Good for FastAPI where objects might be used after commit
)

# Declarative base for ORM models
Base = declarative_base()

# Optional: Functions for explicit engine connect/disconnect if needed by app lifecycle
# async def connect_db():
#     # Engine connects on first use, but explicit connect can be for health checks
#     if async_engine:
#        try:
#            async with async_engine.connect() as conn:
#                await conn.execute(text("SELECT 1"))
#            logger.info("Database connection successful.")
#        except Exception as e:
#            logger.error(f"Database connection failed on startup: {e}", exc_info=True)


# async def disconnect_db():
#     if async_engine:
#         await async_engine.dispose()
#         logger.info("Database engine disposed.")

# The main.py startup/shutdown events might call these. 