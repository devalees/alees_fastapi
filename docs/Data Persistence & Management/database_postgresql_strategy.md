# Database Strategy (PostgreSQL with FastAPI & SQLAlchemy)

## 1. Overview

    * Purpose: To define the selection, configuration, management, usage, scalability, backup, recovery, and availability strategies for the primary relational database (PostgreSQL) supporting the FastAPI-based ERP application.
    * Scope: Covers database choice, SQLAlchemy ORM integration, connection management, general maintenance considerations, strategies for handling growth, and approaches for data protection and service continuity. Schema migration details are covered in `database_migration_strategy.md`.
    * Chosen Technology: **PostgreSQL** (Target Version: 14+ or latest stable), **SQLAlchemy** (Version 2.0+ with asyncio) as the ORM, **`asyncpg`** as the asynchronous database driver.

## 2. Core Requirements

    * Data Persistence, Data Integrity, Transaction Support, Scalability Foundation, JSONB Support.

## 3. Configuration & ORM Integration (Strategic Overview - was Section 3)

    * Pydantic settings for `DATABASE_URL`.
    * SQLAlchemy `async_engine`, `AsyncSessionLocal` factory, and declarative `Base`.
    * FastAPI dependency `get_db_session()`.
    * Model definition conventions.
    * Service layer usage of `AsyncSession`.

## 4. Schema Migrations (Alembic - Reference)

    * All schema changes are managed by **Alembic**. Refer to **`database_migration_strategy.md`** for details.

## 5. Scalability and Growth Management (Strategic Overview - already detailed)

    * Monitoring, Query Optimization, Advanced Indexing, PgBouncer, Vertical Scaling, Read Replicas, Partitioning, Archiving.

## 6. Data Backup, Recovery, and Availability (Strategic Overview - already detailed)

    * Mode A: Self-Managed PostgreSQL (Scripts/Cron or "DB Operations API Module").
    * Mode B: Cloud-Managed PostgreSQL Service (Leverage provider features).
    * General Recovery Principles.

## 7. Security Considerations (Database Focus - Strategic Overview)

    * Strong credentials, least privilege, network access, TLS/SSL.

## 8. Testing Considerations (Pytest - Strategic Overview)

    * Dedicated test DB, fixture-managed schema and sessions. Refer to `testing_environment_setup.md`.

## 9. General Setup Implementation Details (SQLAlchemy & Core DB Integration)

    This section details the foundational code for integrating SQLAlchemy into the FastAPI application.

    ### 9.1. Library Installation
    *   Ensure core SQLAlchemy and driver are in `requirements/base.txt`:
        ```txt
        sqlalchemy[asyncio]>=2.0.0,<2.1.0 # Or latest stable 2.x
        asyncpg>=0.27.0,<0.29.0       # Or latest stable
        ```

    ### 9.2. Pydantic Settings for Database (`app/core/config.py`)
    *   Define `DATABASE_URL` in your `Settings` class.
        ```python
        # app/core/config.py
        # from pydantic import PostgresDsn
        # class Settings(BaseSettings):
        #     # ...
        #     DATABASE_URL: PostgresDsn # e.g., "postgresql+asyncpg://user:pass@host:port/dbname"
        #     DB_ECHO_SQL: bool = False # For debugging SQL in development
        #     # ...
        ```

    ### 9.3. SQLAlchemy Core Setup (`app/core/db.py`)
    *   This module initializes the SQLAlchemy engine, session factory, and declarative base.
        ```python
        # app/core/db.py
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
                pool_size=settings.DB_POOL_SIZE if hasattr(settings.DB_POOL_SIZE, 'DB_POOL_SIZE') else 5, # Example, make configurable
                max_overflow=settings.DB_MAX_OVERFLOW if hasattr(settings.DB_MAX_OVERFLOW, 'DB_MAX_OVERFLOW') else 10, # Example
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
        ```
        *Note: Add `DB_POOL_SIZE` and `DB_MAX_OVERFLOW` to your Pydantic `Settings`.*

    ### 9.4. FastAPI Dependency for Database Sessions (`app/core/dependencies.py`)
    *   This dependency provides a request-scoped `AsyncSession`.
        ```python
        # app/core/dependencies.py
        from typing import AsyncGenerator
        from sqlalchemy.ext.asyncio import AsyncSession
        from app.core.db import AsyncSessionFactory # Import your session factory
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
                 yield None # Or raise an error immediately
                 return

            async with AsyncSessionFactory() as session:
                try:
                    yield session
                    await session.commit()
                except Exception as e:
                    logger.error(f"Database session rollback due to exception: {e}", exc_info=True)
                    await session.rollback()
                    raise # Re-raise the exception to be handled by FastAPI error handlers
                finally:
                    # The session is automatically closed by the `async with AsyncSessionFactory()` context manager
                    pass
        ```

    ### 9.5. Application Startup/Shutdown Events (`app/main.py`)
    *   (Optional but good practice) Test DB connection on startup, dispose engine on shutdown.
        ```python
        # app/main.py
        # from app.core.db import connect_db, disconnect_db # If you implement these

        # @app.on_event("startup")
        # async def on_startup():
        #     # await connect_db() # Optional: Test DB connection
        #     # ... other startup tasks ...

        # @app.on_event("shutdown")
        # async def on_shutdown():
        #     # await disconnect_db() # Dispose engine pool
        #     # ... other shutdown tasks ...
        ```
        *The engine typically manages its pool automatically, so explicit `connect_db/disconnect_db` might not be strictly necessary unless you want an explicit startup check or fine-grained control over disposal.*
## 10. Integration & Usage Patterns (SQLAlchemy in Feature Modules)

    This section provides examples of how SQLAlchemy models are defined and used within feature modules.

    ### 10.1. Defining SQLAlchemy ORM Models
    *   Models are defined in `app/features/<feature_name>/models.py` inheriting from `app.core.db.Base`.
        ```python
        # app/features/products/models.py
        from sqlalchemy import Column, Integer, String, Float, Text, Boolean, DateTime, ForeignKey, func
        from sqlalchemy.orm import Mapped, mapped_column, relationship
        from app.core.db import Base # Import your shared Base
        from typing import Optional, List
        from datetime import datetime
        # from app.core.i18n_base import TranslatableContentMixin # If using the mixin

        # class Product(Base, TranslatableContentMixin): # Example with mixin
        class Product(Base):
            __tablename__ = "products"

            id: Mapped[int] = mapped_column(primary_key=True, index=True)
            sku: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
            # Example for a translatable field (primary lang stored here as per localization strategy)
            name: Mapped[str] = mapped_column(String(255), nullable=False, info={'translatable': True})
            description: Mapped[Optional[str]] = mapped_column(Text, nullable=True, info={'translatable': True})
            price: Mapped[float] = mapped_column(Float, nullable=False)
            is_active: Mapped[bool] = mapped_column(Boolean, default=True)
            created_at: Mapped[datetime] = mapped_column(server_default=func.now())
            updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

            # Example relationship to a Category model
            # category_id: Mapped[Optional[int]] = mapped_column(ForeignKey("categories.id"))
            # category: Mapped[Optional["Category"]] = relationship(back_populates="products")

            # Example relationship to text translations (as per localization strategy)
            # text_translations: Mapped[List["ProductTextTranslation"]] = relationship(
            #     back_populates="parent_product", cascade="all, delete-orphan", lazy="selectin"
            # )
        ```
    *   Use `Mapped` and `mapped_column` for modern, typed SQLAlchemy.
    *   Explicitly name constraints (`ForeignKey(..., name="fk_...")`, `Index("ix_...", ...)` , `UniqueConstraint(..., name="uq_...")` in `__table_args__`) to aid Alembic and database introspection.

    ### 10.2. Basic CRUD Operations in Service Layer (`app/features/<feature_name>/service.py`)
    *   Service functions receive `db: AsyncSession = Depends(get_db_session)`.
        ```python
        # app/features/products/services/product_service.py
        from sqlalchemy.ext.asyncio import AsyncSession
        from sqlalchemy.future import select # For SQLAlchemy 1.4+ style select
        # from sqlalchemy import select # For SQLAlchemy 2.0+ style select
        from typing import List, Optional
        from .. import models, schemas # Pydantic schemas

        # async def get_product_by_id(db: AsyncSession, product_id: int) -> Optional[models.Product]:
        #     result = await db.execute(
        #         select(models.Product).filter(models.Product.id == product_id)
        #     )
        #     return result.scalar_one_or_none()

        # async def get_products(db: AsyncSession, skip: int = 0, limit: int = 100) -> List[models.Product]:
        #     result = await db.execute(
        #         select(models.Product).offset(skip).limit(limit)
        #     )
        #     return result.scalars().all()

        # async def create_product(db: AsyncSession, product_in: schemas.ProductCreate) -> models.Product:
        #     # Note: Translation handling would be more complex as per localization_strategy.md
        #     # This is a simplified example for basic fields.
        #     db_product = models.Product(**product_in.model_dump(exclude={"content_translations"})) # Assuming translations handled separately
        #     db.add(db_product)
        #     # The commit is handled by the get_db_session dependency's exit.
        #     # We need flush to get the ID if it's auto-generated and needed immediately.
        #     await db.flush()
        #     await db.refresh(db_product) # To get DB-generated defaults like created_at
        #
        #     # Placeholder: Here you would call a service to handle creating content_translations
        #     # if product_in.content_translations:
        #     #    await i18n_content_service.save_translations_for_entity(
        #     #        db, db_product, product_in.content_translations, "Product"
        #     #    )
        #     # await db.refresh(db_product, attribute_names=["text_translations"]) # If relationship exists
        #     return db_product

        # async def update_product(
        #    db: AsyncSession, product_db: models.Product, product_in: schemas.ProductUpdate
        # ) -> models.Product:
        #     update_data = product_in.model_dump(exclude_unset=True, exclude={"content_translations"})
        #     for field, value in update_data.items():
        #         setattr(product_db, field, value)
        #     db.add(product_db) # Add to session to mark as dirty
        #     await db.flush()
        #     await db.refresh(product_db)
        #
        #     # Placeholder: Update content_translations
        #     # if product_in.content_translations:
        #     #    await i18n_content_service.update_translations_for_entity(
        #     #        db, product_db, product_in.content_translations, "Product"
        #     #    )
        #     # await db.refresh(product_db, attribute_names=["text_translations"])
        #     return product_db

        # async def delete_product(db: AsyncSession, product_id: int) -> Optional[models.Product]:
        #     product = await get_product_by_id(db, product_id)
        #     if product:
        #         await db.delete(product)
        #         # Commit handled by dependency
        #     return product
        ```

    ### 10.3. Querying with Relationships (Eager Loading)
    *   Use `selectinload` (for collections) or `joinedload` (for one-to-one/many-to-one) in SQLAlchemy queries to prevent N+1 problems when accessing related models that will be serialized.
        ```python
        # from sqlalchemy.orm import selectinload

        # async def get_product_with_category(db: AsyncSession, product_id: int):
        #     stmt = (
        #         select(models.Product)
        #         .options(selectinload(models.Product.category)) # Assuming 'category' relationship
        #         .filter(models.Product.id == product_id)
        #     )
        #     result = await db.execute(stmt)
        #     return result.scalar_one_or_none()
        ```

    ### 10.4. Handling Database Integrity Errors
    *   Service layers should be prepared to catch `sqlalchemy.exc.IntegrityError` (e.g., for unique constraint violations) and translate them into appropriate HTTPExceptions (e.g., `409 Conflict`).
        ```python
        # from sqlalchemy.exc import IntegrityError
        # from fastapi import HTTPException, status

        # async def create_user_service(db: AsyncSession, user_in: schemas.UserCreate):
        #     try:
        #         # ... create user_db object and add to session ...
        #         await db.flush() # Try to save to DB to trigger constraints
        #         await db.refresh(user_db)
        #         return user_db
        #     except IntegrityError as e:
        #         await db.rollback() # Important to rollback before raising HTTP error
        #         if "uq_users_email" in str(e.orig): # Check specific constraint name if possible
        #             raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered.")
        #         # logger.error(f"Database integrity error: {e}", exc_info=True)
        #         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database integrity error.")
        ```

    ### 10.5. Using `info={'translatable': True}`
    *   The localization service will introspect models for fields with `info={'translatable': True}` to determine which fields to handle for content translation, as per `localization_strategy.md`.

