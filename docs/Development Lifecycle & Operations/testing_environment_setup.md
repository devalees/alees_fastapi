# Testing Environment Setup & Configuration (Pytest with FastAPI, SQLAlchemy, Alembic)

## 1. Overview

- **Purpose**: To define the setup, configuration, and dependencies for the project's testing environment, enabling unit, integration, and API testing for the FastAPI application using **Pytest**. This setup utilizes **PostgreSQL** as the test database backend, managed via **SQLAlchemy** and **Alembic**.
- **Scope**: Covers required libraries, Pytest configuration, test-specific application settings (via Pydantic Settings), test database setup and teardown, test data utilities (Factory-Boy), and fixture conventions.
- **Goal**: Ensure a consistent, reliable, efficient, and production-parity (where appropriate) testing environment for developers and the CI/CD pipeline, allowing for comprehensive testing of the FastAPI application.

## 2. Core Testing Stack Components

- **Test Runner:** **Pytest** (`pytest`)
- **Async Support:** **`pytest-asyncio`**
- **API Testing Client:** FastAPI's `TestClient` (uses `httpx`)
- **Database ORM:** SQLAlchemy (with `asyncpg` driver for PostgreSQL)
- **Database Migrations:** Alembic
- **Application Configuration:** Pydantic Settings (`pydantic-settings`)
- **Test Data Generation:** `factory-boy`
- **Mocking:** `pytest-mock` (using `unittest.mock`)
- **Coverage:** `pytest-cov`

## 3. Dependency Management (`requirements/`)

1.  **`requirements/base.txt` (Core dependencies also used by tests):**

    ```txt
    # ... (fastapi, uvicorn, pydantic, pydantic-settings)
    sqlalchemy[asyncio]>=2.0.0,<2.1.0
    asyncpg>=0.27.0,<0.28.0 # PostgreSQL async driver
    alembic>=1.11.0,<1.12.0
    # ... (celery, redis, etc. if integration tested)
    ```

2.  **`requirements/test.txt` (Test-specific dependencies):**

    ```txt
    # Base testing framework
    pytest>=7.4.0,<8.0.0
    pytest-asyncio>=0.21.0,<0.22.0 # For testing async code
    pytest-cov>=4.1.0,<5.0.0     # For code coverage
    pytest-mock>=3.11.0,<4.0.0    # For mocking

    # HTTP client for TestClient (FastAPI's TestClient uses httpx)
    httpx>=0.24.0,<0.25.0

    # Test data generation
    factory-boy>=3.2.0,<3.3.0
    # pytest-factoryboy>=2.5.0,<2.6.0 # Optional: for easier fixture generation

    # Optional (Add if explicitly needed for specific test types)
    # freezegun>=1.2.0,<1.3.0
    # pytest-celery>=0.0.0 # (Ensure compatibility with your Celery setup)
    # fakeredis[aioredis]>=2.20.0,<2.21.0 # For faking Redis
    # sqlalchemy-utils # If using for test database creation/dropping utilities
    ```

3.  **Inclusion:** `requirements/dev.txt` should include `-r base.txt` and `-r test.txt`. The CI pipeline will install dependencies from `requirements/dev.txt` or `requirements/base.txt` + `requirements/test.txt`.

## 4. Pytest Configuration (`pytest.ini` or `pyproject.toml`)

Create `pytest.ini` (or use `[tool.pytest.ini_options]` in `pyproject.toml`):

```ini
[pytest]
# Set environment variables specifically for the test run if needed
# Example: Overriding the .env file Pydantic Settings might try to load
env =
    ENVIRONMENT=test
    # Optionally: OVERRIDE_DOT_ENV_FILE=.env.test (if you want a specific .env for tests)

python_files = tests.py test_*.py *_test.py
python_classes = Test*
python_functions = test_*

# Required for pytest-asyncio default mode (all tests treated as async)
# asyncio_mode = auto # or 'strict'

# Example: Configure pytest-cov options
addopts = --cov=app --cov-report=term-missing --cov-report=xml --cov-fail-under=80 -ra -q

# Optional: Register custom markers
markers =
    slow: marks tests as slow to run
    integration: marks integration tests
    api: marks API tests
    unit: marks unit tests
```

- `env`: Can be used to set environment variables that Pydantic Settings will pick up, ensuring a test-specific configuration loads.
- `asyncio_mode = auto`: Simplifies running `async def` test functions.

## 5. Test Application Settings (`app/core/config.py` and Overrides)

- The main `app/core/config.py:Settings` class defines all configurations.
- For tests, Pydantic Settings will load values based on:
  1.  Environment variables set by `pytest.ini`'s `env` section or by the CI runner.
  2.  A dedicated `.env.test` file if `OVERRIDE_DOT_ENV_FILE=.env.test` is set and `Settings.model_config.env_file` is configured to respect such an override (or you have a separate `TestSettings(Settings)` class).
  3.  Default values in the `Settings` class.
- **Key Test-Specific Settings (ensured via environment variables or a `.env.test`):**
  - `ENVIRONMENT="test"`
  - `DEBUG_MODE=False` (usually for tests, unless debugging a specific test)
  - `DATABASE_URL`: **Must point to a dedicated test PostgreSQL database.** Example: `postgresql+asyncpg://test_user:test_pass@localhost:5433/erp_test_db` (note different port or DB name).
  - `CELERY_TASK_ALWAYS_EAGER=True` (for Celery: run tasks synchronously in tests).
  - `CELERY_TASK_EAGER_PROPAGATES=True` (for Celery: propagate exceptions from eager tasks).
  - Disable or mock external service calls: Sentry DSN set to None, mock API keys for external services.
  - Redis settings might point to a specific test DB number or `fakeredis`.

## 6. Test Database Setup & Teardown (PostgreSQL with Alembic/SQLAlchemy)

This is the most complex part compared to `pytest-django`.

- **Strategy**: Create the test database schema once per test session (or module) for efficiency. Each test function should run in its own transaction that is rolled back.
- **Pytest Fixtures (`tests/conftest.py`):**

  ```python
  # tests/conftest.py
  import asyncio
  import pytest
  from typing import AsyncGenerator, Generator
  from httpx import AsyncClient
  from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
  from sqlalchemy.orm import sessionmaker
  from sqlalchemy import text

  from app.main import app # Your FastAPI application instance
  from app.core.config import settings # Your Pydantic settings
  from app.core.db import Base, get_db_session # Your SQLAlchemy Base and DB session dependency

  # 1. Configure Engine for Test Database
  # Ensure DATABASE_URL in settings points to your TEST database for this fixture
  # This usually means settings are overridden via environment variables for the test run
  test_engine = create_async_engine(settings.DATABASE_URL, echo=False) # Can set echo=True for debugging SQL
  AsyncTestingSessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

  # 2. Fixture to Create/Drop Tables (Session-Scoped for efficiency)
  @pytest.fixture(scope="session")
  def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
      """Create an instance of the default event loop for each test session."""
      loop = asyncio.get_event_loop_policy().new_event_loop()
      yield loop
      loop.close()

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

      yield # Tests run here

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
          await transaction.rollback() # Rollback changes after each test
          await connection.close()

  # 4. Override get_db_session dependency for tests
  # This ensures that your API endpoints use the transactional test session
  async def override_get_db_session() -> AsyncGenerator[AsyncSession, None]:
      """Overrides the get_db_session dependency to use the test session."""
      async with AsyncTestingSessionLocal() as session:
          # This is a simplified version for override; for transaction control per test,
          # the `db_session` fixture above is better if it can be directly injected
          # into services. If overriding app dependency, careful management of the
          # connection/transaction lifecycle is needed.
          # The `db_session` fixture is intended for direct use in test functions.
          # For overriding app dependencies, it's often:
          connection = await test_engine.connect()
          transaction = await connection.begin_nested() # Use nested for savepoints if needed, or begin()

          async_session_factory = async_sessionmaker(bind=connection, autoflush=False, autocommit=False)
          test_session = async_session_factory()

          try:
              yield test_session
              # Note: Commit/rollback is usually handled by the test structure or the main session fixture
          except Exception:
              await test_session.rollback()
              raise
          finally:
              await test_session.close()
              # Rollback the outer transaction if it wasn't committed explicitly in a test needing commit
              if transaction.is_active: # Check if not already rolled back or committed
                  await transaction.rollback()
              await connection.close()


  app.dependency_overrides[get_db_session] = override_get_db_session

  # 5. API Test Client Fixture
  @pytest.fixture(scope="function")
  async def test_client() -> AsyncGenerator[AsyncClient, None]:
      """Provides an httpx.AsyncClient for making API requests to the test app."""
      async with AsyncClient(app=app, base_url="http://test") as client:
          yield client
  ```

- **Database User Permissions:** The PostgreSQL user for the test database needs privileges to `CREATE` and `DROP` tables (if using `Base.metadata.create_all/drop_all`) or run DDL via Alembic.
- **Alembic `script.py.mako`:** Ensure your Alembic template doesn't try to import application code that initializes a non-test DB connection when Alembic generates new revisions.

## 7. Factory-Boy Setup (`tests/factories.py` or per-feature `tests/factories.py`)

- Define factories inheriting from `factory.alchemy.SQLAlchemyModelFactory` for SQLAlchemy models.
- Configure the session for factories:

  ```python
  # tests/factories.py (example)
  # import factory
  # from factory.alchemy import SQLAlchemyModelFactory
  # from app.features.users.models import User
  # from tests.conftest import AsyncTestingSessionLocal # Your test session factory

  # class BaseFactory(SQLAlchemyModelFactory):
  #     class Meta:
  #         abstract = True
  #         sqlalchemy_session_persistence = "flush" # Flush to DB but don't commit within factory
  #         # The session is managed by the db_session fixture

  # @pytest.fixture(scope="function", autouse=True) # Ensure session is set for factories
  # async def set_factoryboy_session(db_session: AsyncSession):
  #    BaseFactory._meta.sqlalchemy_session = db_session # Assign the transactional session

  # class UserFactory(BaseFactory):
  #     class Meta:
  #         model = User
  #     id = factory.Sequence(lambda n: n)
  #     email = factory.LazyAttribute(lambda obj: f"user{obj.id}@example.com")
  #     # ... other fields
  ```

  The `set_factoryboy_session` fixture ensures factories use the per-test transactional session.

## 8. Running Tests

- From the project root: `pytest`
- Docker Compose: `docker-compose run --rm api pytest`
- **Requirement:** A PostgreSQL server must be running and accessible with connection details matching the test `DATABASE_URL`. The `setup_test_database` fixture will handle schema creation.

## 9. CI Configuration

- The CI pipeline must:
  - Install dependencies from `requirements/dev.txt` (or `base.txt` + `test.txt`).
  - **Provide a PostgreSQL service.**
  - **Set environment variables for test configuration** (e.g., `ENVIRONMENT=test`, `DATABASE_URL` pointing to the CI PostgreSQL service).
  - Execute tests using `pytest`.
