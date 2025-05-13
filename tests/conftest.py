import asyncio
import pytest
from typing import AsyncGenerator, Generator
from httpx import AsyncClient
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text

from app.main import app  # Your FastAPI application instance
from app.core.config import settings  # Your Pydantic settings
from app.core.db import Base  # Your SQLAlchemy Base
from app.core.dependencies import get_db_session  # Your DB session dependency

# 1. Configure Engine for Test Database
# Ensure DATABASE_URL in settings points to your TEST database for this fixture
test_engine = create_async_engine(
    settings.DATABASE_URL.render_as_string(hide_password=False)
        if hasattr(settings.DATABASE_URL, 'render_as_string')
        else str(settings.DATABASE_URL),
    echo=False  # Can set echo=True for debugging SQL
)
AsyncTestingSessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

# 2. Using pytest-asyncio's built-in event_loop fixture with loop_scope = "session"
# No need to define a custom event_loop fixture

@pytest.fixture(scope="session", autouse=True)
async def setup_test_database():
    """
    Creates all tables at the beginning of the test session and drops them at the end.
    Alternatively, run Alembic migrations here.
    """
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # To use Alembic for schema creation (more robust for reflecting actual migrations):
        # from alembic.config import Config
        # from alembic import command
        # alembic_cfg = Config("alembic.ini") # Ensure alembic.ini sqlalchemy.url is also test DB
        # command.upgrade(alembic_cfg, "head")

    yield  # Tests run here

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        # To use Alembic for teardown (if you used it for setup):
        # command.downgrade(alembic_cfg, "base")

    await test_engine.dispose()


# 3. Fixture for a Test Database Session (Function-Scoped with Transaction Rollback)
@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Provides a database session for a test, wrapped in a transaction that is rolled back.
    """
    connection = await test_engine.connect()
    transaction = await connection.begin()
    session = AsyncTestingSessionLocal(bind=connection)

    try:
        yield session
    finally:
        await session.close()
        await transaction.rollback()  # Rollback changes after each test
        await connection.close()

# 4. Override get_db_session dependency for tests
# This ensures that your API endpoints use the transactional test session
async def override_get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Overrides the get_db_session dependency to use the test session."""
    connection = await test_engine.connect()
    transaction = await connection.begin_nested()  # Use nested for savepoints if needed

    async_session_factory = async_sessionmaker(bind=connection, autoflush=False, autocommit=False)
    test_session = async_session_factory()

    try:
        yield test_session
    except Exception:
        await test_session.rollback()
        raise
    finally:
        await test_session.close()
        # Rollback the outer transaction
        if transaction.is_active:  # Check if not already rolled back or committed
            await transaction.rollback()
        await connection.close()


app.dependency_overrides[get_db_session] = override_get_db_session

# 5. API Test Client Fixture
@pytest.fixture(scope="function")
async def test_client() -> AsyncGenerator[AsyncClient, None]:
    """Provides an httpx.AsyncClient for making API requests to the test app."""
    # Create a TestClient for FastAPI
    test_client = TestClient(app)
    
    # Create AsyncClient that will use the base_url
    async with AsyncClient(base_url="http://test") as ac:
        # For each request made with AsyncClient, 
        # actually execute it through the FastAPI TestClient
        original_request = ac.request
        
        async def patched_request(*args, **kwargs):
            method = args[0] if args else kwargs.get("method", "GET")
            url = args[1] if len(args) > 1 else kwargs.get("url", "")
            # Remove base_url if it's included
            if str(url).startswith(str(ac.base_url)):
                url = str(url)[len(str(ac.base_url)):]
            # Use the TestClient to execute the request
            response = test_client.request(method=method, url=url, **kwargs)
            return response
        
        # Replace the request method
        ac.request = patched_request
        
        yield ac 