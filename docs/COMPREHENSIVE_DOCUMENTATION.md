# Alees FastAPI Project Documentation

## Table of Contents

1. [Getting Started & Setup](#1-getting-started--setup)
   - [Development Setup Guide](#11-development-setup-guide)
   - [Testing Environment Setup](#12-testing-environment-setup)

2. [Core Architecture & Configuration](#2-core-architecture--configuration)
   - [Configuration Management Strategy](#21-configuration-management-strategy)
   - [Secrets Management Strategy](#22-secrets-management-strategy)
   - [API Strategy](#23-api-strategy)
   - [Validation Strategy](#24-validation-strategy)

3. [Data Layer](#3-data-layer)
   - [Database PostgreSQL Strategy](#31-database-postgresql-strategy)
   - [Migration and DB Management Strategy](#32-migration-and-db-management-strategy)
   - [Cache Redis](#33-cache-redis)
   - [File Storage](#34-file-storage)

4. [Application Services](#4-application-services)
   - [Asynchronous Celery](#41-asynchronous-celery)
   - [Email Service Integration](#42-email-service-integration)
   - [Search Strategy](#43-search-strategy)
   - [Real-time Strategy](#44-real-time-strategy)
   - [Feature Flags Strategy](#45-feature-flags-strategy)
   - [Localization Strategy](#46-localization-strategy)
   - [Logging Strategy](#47-logging-strategy)

5. [Development & Operations](#5-development--operations)
   - [Testing Strategy TDD](#51-testing-strategy-tdd)
   - [Security Strategy](#52-security-strategy)
   - [Monitoring Strategy](#53-monitoring-strategy)
   - [Deployment Strategy and CI/CD](#54-deployment-strategy-and-cicd)

---

## 1. Getting Started & Setup

### 1.1 Development Setup Guide

#### Overview

- **Purpose**: To provide step-by-step instructions for developers to set up the FastAPI-based ERP backend project and its dependencies on their local machine for development and testing.
- **Goal**: Enable developers to quickly get a working, consistent development environment running that mirrors the core technologies used in staging/production where feasible (PostgreSQL, Redis, Celery, Elasticsearch).
- **Primary Method**: Utilize **Docker** and **Docker Compose** to orchestrate required services and the application container.

#### Prerequisites

- **Git**: Must be installed ([https://github.com/devalees/alees_fastapi.git](https://git-scm.com/)).
- **Docker & Docker Compose**: Must be installed and running ([https://www.docker.com/products/docker-desktop/](https://www.docker.com/products/docker-desktop/)). Ensure sufficient resources (RAM/CPU) are allocated to Docker Desktop.
- **Python (Optional, for local tools/IDE integration):** A recent version compatible with the project (e.g., Python 3.10+) installed locally can be helpful for IDE features (linting, type checking outside the container) and running some standalone scripts, but primary development and execution occur _inside_ the Docker container.
- **Code Editor/IDE**: VS Code (with Dev Containers extension recommended), PyCharm Professional (with Docker integration), or similar.
- **(Optional) `make`**: A `Makefile` can be provided in the project root to simplify common Docker Compose commands (e.g., `make build`, `make up`, `make logs`, `make test`).

#### Initial Setup Steps

1. **Clone Repository:**
   ```bash
   git clone <your_repository_url> erp_fastapi_project
   cd erp_fastapi_project
   ```

2. **Environment Configuration (`.env` file):**
   - Copy the example environment file: `cp .env.example .env`
   - **Review and Edit `.env`:** Open the `.env` file in your editor.
   - Fill in necessary values, especially:
     - `DATABASE_URL`: Verify it matches the PostgreSQL service credentials and port defined in `docker-compose.yml` (e.g., `postgresql+asyncpg://erp_user:erp_pass@localhost:5432/erp_dev_db`).
     - `REDIS_HOST`, `REDIS_PORT`, `REDIS_PASSWORD` (if any for local Redis).
     - `JWT_SECRET_KEY`: Generate a strong, random secret key (e.g., using `openssl rand -hex 32`). **Do not use the example key from `.env.example` for anything other than initial testing if it's weak.**
     - Other settings from `app/core/config.py:Settings` that might need local overrides (e.g., `DEBUG_MODE=True`, `ENVIRONMENT=development`).
   - **Important:** The `.env` file is ignored by Git (via `.gitignore`) and must **never** be committed with actual secrets.

3. **Build Docker Images:**
   - Build the application image and any other custom images defined in `docker-compose.yml`.
   - Command: `docker-compose build`
     - (Or `make build` if a Makefile target exists)

4. **Start Background Services:**
   - Start the background services (PostgreSQL, Redis, optionally Elasticsearch for local search dev) defined in `docker-compose.yml`.
   - Command: `docker-compose up -d postgres redis es01` (Replace service names with actual names from your `docker-compose.yml`. `es01` is a common name for a single-node Elasticsearch dev instance).
   - Wait a few seconds for them to initialize fully. Check logs with `docker-compose logs postgres redis es01`.

5. **Run Initial Database Migrations (Alembic):**
   - Run Alembic migrations _inside_ the application container to set up the database schema. The `api` service (or whatever you name your FastAPI app service in `docker-compose.yml`) will need access to the database.
   - Command: `docker-compose run --rm api alembic upgrade head`
     - (Or `make migrate` if a Makefile target exists)

6. **Create Initial User/Seed Data (Optional but Recommended):**
   - If you have scripts or custom Alembic data migrations to create an initial admin user or seed essential lookup data (e.g., default roles, organization types):
   - Command: `docker-compose run --rm api python -m app.scripts.seed_initial_data` (if you create such a script)
     - Or, if it's an Alembic data migration, it would have been run in the previous step.
   - To create a superuser, you might have a CLI command exposed via Typer/Click within your app, callable like: `docker-compose run --rm api python -m app.cli users create-superuser --username admin --email admin@example.com --password changeme`

7. **Start Development Server (FastAPI with Uvicorn):**
   - Start the main FastAPI application server (running inside the `api` container). This will typically run Uvicorn with live reloading enabled for development.
   - Command: `docker-compose up api`
     - (Or `make up-api` or just `make up` if it includes the API service)
   - The `docker-compose.yml` for the `api` service should specify a command like:
     `command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir /app/app`
   - Access the application at `http://localhost:8000` (or the mapped port). The OpenAPI docs will typically be at `http://localhost:8000/docs` or `/redoc`.

#### Common Development Tasks

- **Running Tests (Pytest):**
  ```bash
  docker-compose run --rm api pytest
  # Or to run tests for a specific path/file:
  docker-compose run --rm api pytest app/features/users/tests/test_router.py
  # Or using make:
  # make test
  # make test path=app/features/users/tests/test_router.py
  ```

- **Generating Alembic Migrations:**
  1. Make changes to your SQLAlchemy models in `app/.../models.py`.
  2. Generate a new revision:
     ```bash
     docker-compose run --rm api alembic revision -m "add_new_field_to_products"
     # For autogenerate (review carefully!):
     docker-compose run --rm api alembic revision --autogenerate -m "auto_add_new_field_to_products"
     ```
  3. **Crucially, inspect and edit the generated migration script** in `alembic/versions/`.
  4. Apply the migration locally:
     ```bash
     docker-compose run --rm api alembic upgrade head
     ```

- **Running Linters/Formatters:**
  ```bash
  docker-compose run --rm api ruff check .
  docker-compose run --rm api ruff format .
  docker-compose run --rm api mypy .
  # Or make targets: make lint, make format
  ```

- **Running Celery Worker:**
  ```bash
  docker-compose run --rm celery_worker celery -A app.core.celery_config.celery_app worker -l INFO -P eventlet
  ```

- **Running Celery Beat:**
  ```bash
  docker-compose run --rm celery_beat celery -A app.core.celery_config.celery_app beat -l INFO --scheduler app.tasks.db_scheduler.DatabaseScheduler
  ```

- **Accessing Python Shell/REPL:**
  ```bash
  docker-compose run --rm api ipython
  ```

- **Stopping Services:**
  ```bash
  docker-compose down # Stops and removes containers, networks, and default volumes
  # or
  docker-compose stop # Stops containers without removing them
  ```

- **Accessing Database:**
  ```bash
  psql postgresql://erp_user:erp_pass@localhost:5432/erp_dev_db
  ```

- **Accessing Redis:**
  ```bash
  redis-cli -h localhost -p 6379
  ```

#### IDE Integration

- If using VS Code, setting up a `.devcontainer/devcontainer.json` configuration allows you to develop directly _inside_ the running `api` Docker container.
- This provides a consistent environment with all tools (Python, linters, formatters, test runners) available directly, matching the container's setup.
- The `devcontainer.json` would specify the Docker Compose service to use (e.g., `api`), extensions to install, and post-create commands.

#### Adding New Features

1. **Creating a New Feature Module:**
   ```
   app/features/new_feature/
   ├── __init__.py
   ├── router.py       # FastAPI router definition
   ├── schemas.py      # Pydantic models for API I/O
   ├── models.py       # SQLAlchemy ORM models
   ├── service.py      # Business logic 
   └── exceptions.py   # Feature-specific exceptions
   ```

2. **Implementing Database Models:**
   - Extend `BaseModel` from `app.core.base_models` for consistent ID and timestamp fields
   - After defining models, generate and review migrations with Alembic

3. **Adding Background Tasks:**
   - Create task functions in a `tasks.py` file within your feature module
   - Register the module in Celery's `autodiscover_tasks` if not already included

4. **Writing Tests:**
   - Follow the established test structure with unit/integration/api directories
   - Make use of test factories (in `tests/factories/`) for consistent test data

#### Debugging Tips

- **FastAPI Application:**
  - Check the application logs: `docker-compose logs -f api`
  - Use the `--reload` flag for Uvicorn (included in development configuration) to automatically reload on code changes
  - For in-depth debugging, configure your IDE's remote debugger to connect to the Docker container

- **Database Issues:**
  - Inspect the database directly using `psql` or a GUI tool
  - Review Alembic migration files in `alembic/versions/` 
  - Check connection settings in your `.env` file
  - For a fresh start: `docker-compose down -v` to remove volumes, then recreate and run migrations again

- **API Endpoint Testing:**
  - Use the Swagger UI at `/docs` or ReDoc at `/redoc`
  - For more complex API scenarios, create collections in Postman or use `httpx` in scripts

#### Troubleshooting Tips

- **Ensure Docker Desktop is running** and has sufficient resources allocated (CPU, Memory).
- **Verify `.env` file:** Ensure variables are correctly set and match `docker-compose.yml` service definitions.
- **Check Container Logs:** If services fail to start or behave unexpectedly, check logs: `docker-compose logs <service_name>`.
- **Rebuild Images:** If you change `Dockerfile` or installed dependencies: `docker-compose build --no-cache <service_name>`.
- **Clean Up Docker Resources:** Occasionally, prune unused Docker images, containers, volumes, and networks: `docker system prune -a --volumes`.
- **Port Conflicts:** Ensure ports mapped in `docker-compose.yml` (e.g., 8000, 5432, 6379) are not already in use on your host machine.
- **Permission Issues:** Some systems may encounter permission problems with mounted volumes. Solutions include:
  - Setting appropriate user permissions in the Dockerfile
  - Using Docker Compose's `user` option to match your host UID/GID
  - Adjusting volume mount permissions in Docker settings

#### Best Practices for Development

- **Version Control:**
  - Create feature branches for each new feature or bugfix
  - Keep commits focused and descriptive
  - Run linters and tests before pushing code

- **Code Quality:**
  - Follow the established project structure and patterns
  - Use type hints consistently throughout the codebase
  - Write comprehensive docstrings for public functions and classes
  - Configure pre-commit hooks for automated code quality checks

- **Security:**
  - Never commit sensitive information to the repository
  - Regularly update dependencies to address security vulnerabilities
  - Follow secure coding practices, especially for authentication/authorization

- **Documentation:**
  - Keep API documentation up to date (FastAPI generates this automatically)
  - Add comments for complex business logic
  - Document architecture decisions in appropriate markdown files

### 1.2 Testing Environment Setup

#### Overview

- **Purpose**: To define the setup, configuration, and dependencies for the project's testing environment, enabling unit, integration, and API testing for the FastAPI application using **Pytest**. This setup utilizes **PostgreSQL** as the test database backend, managed via **SQLAlchemy** and **Alembic**.
- **Scope**: Covers required libraries, Pytest configuration, test-specific application settings (via Pydantic Settings), test database setup and teardown, test data utilities (Factory-Boy), and fixture conventions.
- **Goal**: Ensure a consistent, reliable, efficient, and production-parity (where appropriate) testing environment for developers and the CI/CD pipeline, allowing for comprehensive testing of the FastAPI application.

#### Core Testing Stack Components

- **Test Runner:** **Pytest** (`pytest`)
- **Async Support:** **`pytest-asyncio`**
- **API Testing Client:** FastAPI's `TestClient` (uses `httpx`)
- **Database ORM:** SQLAlchemy (with `asyncpg` driver for PostgreSQL)
- **Database Migrations:** Alembic
- **Application Configuration:** Pydantic Settings (`pydantic-settings`)
- **Test Data Generation:** `factory-boy`
- **Mocking:** `pytest-mock` (using `unittest.mock`)
- **Coverage:** `pytest-cov`

#### Dependency Management

1. **`requirements/base.txt` (Core dependencies also used by tests):**
   ```txt
   # ... (fastapi, uvicorn, pydantic, pydantic-settings)
   sqlalchemy[asyncio]>=2.0.0,<2.1.0
   asyncpg>=0.27.0,<0.28.0 # PostgreSQL async driver
   alembic>=1.11.0,<1.12.0
   # ... (celery, redis, etc. if integration tested)
   ```

2. **`requirements/test.txt` (Test-specific dependencies):**
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

3. **Inclusion:** `requirements/dev.txt` should include `-r base.txt` and `-r test.txt`. The CI pipeline will install dependencies from `requirements/dev.txt` or `requirements/base.txt` + `requirements/test.txt`.

#### Pytest Configuration

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

#### Test Application Settings

- The main `app/core/config.py:Settings` class defines all configurations.
- For tests, Pydantic Settings will load values based on:
  1. Environment variables set by `pytest.ini`'s `env` section or by the CI runner.
  2. A dedicated `.env.test` file if `OVERRIDE_DOT_ENV_FILE=.env.test` is set and `Settings.model_config.env_file` is configured to respect such an override (or you have a separate `TestSettings(Settings)` class).
  3. Default values in the `Settings` class.

**Key Test-Specific Settings:**
- `ENVIRONMENT="test"`
- `DEBUG_MODE=False` (usually for tests, unless debugging a specific test)
- `DATABASE_URL`: **Must point to a dedicated test PostgreSQL database.** Example: `postgresql+asyncpg://test_user:test_pass@localhost:5433/erp_test_db` (note different port or DB name).
- `CELERY_TASK_ALWAYS_EAGER=True` (for Celery: run tasks synchronously in tests).
- `CELERY_TASK_EAGER_PROPAGATES=True` (for Celery: propagate exceptions from eager tasks).
- Disable or mock external service calls: Sentry DSN set to None, mock API keys for external services.
- Redis settings might point to a specific test DB number or `fakeredis`.

#### Test Database Setup & Teardown

**Strategy**: Create the test database schema once per test session (or module) for efficiency. Each test function should run in its own transaction that is rolled back.

**Pytest Fixtures (`tests/conftest.py`):**

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
test_engine = create_async_engine(settings.DATABASE_URL, echo=False)
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
    """Creates all tables at the beginning of the test session and drops them at the end."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield # Tests run here

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await test_engine.dispose()

# 3. Fixture for a Test Database Session
@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provides a database session for a test, wrapped in a transaction that is rolled back."""
    connection = await test_engine.connect()
    transaction = await connection.begin()
    session = AsyncTestingSessionLocal(bind=connection)

    try:
        yield session
    finally:
        await session.close()
        await transaction.rollback()
        await connection.close()

# 4. Override get_db_session dependency for tests
async def override_get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Overrides the get_db_session dependency to use the test session."""
    async with AsyncTestingSessionLocal() as session:
        connection = await test_engine.connect()
        transaction = await connection.begin_nested()

        async_session_factory = async_sessionmaker(bind=connection, autoflush=False, autocommit=False)
        test_session = async_session_factory()

        try:
            yield test_session
        except Exception:
            await test_session.rollback()
            raise
        finally:
            await test_session.close()
            if transaction.is_active:
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

#### Factory-Boy Setup

Define factories inheriting from `factory.alchemy.SQLAlchemyModelFactory` for SQLAlchemy models:

```python
# tests/factories.py (example)
import factory
from factory.alchemy import SQLAlchemyModelFactory
from app.features.users.models import User
from tests.conftest import AsyncTestingSessionLocal

class BaseFactory(SQLAlchemyModelFactory):
    class Meta:
        abstract = True
        sqlalchemy_session_persistence = "flush"
        # The session is managed by the db_session fixture

@pytest.fixture(scope="function", autouse=True)
async def set_factoryboy_session(db_session: AsyncSession):
    BaseFactory._meta.sqlalchemy_session = db_session

class UserFactory(BaseFactory):
    class Meta:
        model = User

    email = factory.Faker('email')
    username = factory.Faker('user_name')
    is_active = True
```

## 2. Core Architecture & Configuration

### 2.1 Configuration Management Strategy

#### Overview

- **Purpose**: To define the strategy for managing application configuration settings across different environments (development, testing, staging, production) in a consistent, secure, and maintainable manner for the FastAPI-based ERP system.
- **Scope**: Covers management of application settings, environment variables, and sensitive credentials (secrets) integration.
- **Goal**: Ensure the application behaves correctly in each environment, secrets are handled securely, configuration is easy to manage and deploy, and environment differences are clearly defined using Pydantic Settings.

#### Core Principles

- **Environment Parity (Strive for):** Keep development, staging, and production environments as similar as possible regarding configuration structure, varying only environment-specific values.
- **Configuration in Environment:** Store environment-specific configuration (especially secrets, hostnames, resource locators) in the **environment**, not in version-controlled code.
- **Explicit Configuration:** Rely on explicitly defined settings. Pydantic Settings enforces this by requiring fields to be declared.
- **Security:** Treat all sensitive configuration values (passwords, API keys, cryptographic keys) as secrets, managed via a secure mechanism.
- **Consistency:** Use a consistent method (Pydantic Settings instance) for accessing configuration values throughout the application code.
- **Immutability (Ideal):** Configuration ideally doesn't change frequently after deployment without a new code release or explicit configuration update process impacting the environment.

#### Configuration Layers & Tools

##### Pydantic Settings (`app/core/config.py`)

- **Primary Tool:** The `pydantic-settings` library will be used.
- **Structure:** A single `Settings` class (inheriting from `pydantic_settings.BaseSettings`) will define all application configuration variables with Python type hints and optional default values.

```python
# app/core/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional

class Settings(BaseSettings):
    # Application Core
    APP_NAME: str = "FastAPI ERP"
    DEBUG_MODE: bool = False
    ENVIRONMENT: str = "development" # e.g., development, test, staging, production
    API_V1_PREFIX: str = "/api/v1"
    TIME_ZONE: str = "UTC"

    # Database
    DATABASE_URL: str # Must be provided via env or .env

    # Redis (Cache & Celery Broker/Backend, Rate Limiting)
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: Optional[str] = None
    REDIS_CACHE_DB: int = 1
    REDIS_CELERY_BROKER_DB: int = 0
    REDIS_CELERY_RESULT_DB: int = 0 # Can be same as broker
    REDIS_RATE_LIMIT_DB: int = 2
    REDIS_MAX_CONNECTIONS: int = 20

    # Construct full URLs from components
    @property
    def REDIS_CACHE_URL(self) -> str:
        return f"redis://{':' + self.REDIS_PASSWORD + '@' if self.REDIS_PASSWORD else ''}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_CACHE_DB}"

    @property
    def CELERY_BROKER_URL(self) -> str:
        return f"redis://{':' + self.REDIS_PASSWORD + '@' if self.REDIS_PASSWORD else ''}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_CELERY_BROKER_DB}"

    @property
    def CELERY_RESULT_BACKEND(self) -> str:
        return f"redis://{':' + self.REDIS_PASSWORD + '@' if self.REDIS_PASSWORD else ''}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_CELERY_RESULT_DB}"

    # JWT Authentication
    JWT_SECRET_KEY: str # Must be provided
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # API Behavior
    API_PAGINATION_DEFAULT_SIZE: int = 20
    API_PAGINATION_MAX_SIZE: int = 100
    API_RATE_LIMIT_USER: str = "1000/hour"
    API_RATE_LIMIT_ANONYMOUS: str = "100/hour"

    # CORS
    CORS_ALLOWED_ORIGINS: List[str] = ["http://localhost:3000"] # Example frontend

    # File Storage
    FILE_STORAGE_BACKEND: str = "local"  # "local" or "s3"
    LOCAL_MEDIA_ROOT: str = "/app/media"
    LOCAL_MEDIA_URL_PREFIX: str = "/media"

    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None # Handled by secrets management
    AWS_S3_BUCKET_NAME: Optional[str] = None
    AWS_S3_REGION_NAME: Optional[str] = None
    AWS_S3_ENDPOINT_URL: Optional[str] = None # For MinIO
    AWS_S3_PRESIGNED_URL_EXPIRY_SECONDS: int = 3600

    # Monitoring
    SENTRY_DSN: Optional[str] = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding='utf-8',
        extra='ignore', # Ignore extra env vars not defined in the model
        case_sensitive=False # Environment variables are typically case-insensitive
    )

settings = Settings() # Single, importable instance
```

##### Environment Variables & `.env` File

- **Primary Mechanism for Overrides:** Environment variables are the primary method for injecting environment-specific configuration and secrets into the application, overriding defaults or `.env` values.
- **`.env` File:**
  - Used _only_ for local development.
  - Contains environment variables, including secrets for local development instances.
  - **Must be added to `.gitignore`**.
  - A `.env.example` file **must** be committed to Git, showing all required variables without their actual values.

Example `.env.example`:
```
# .env.example
APP_NAME=FastAPI ERP (Dev)
DEBUG_MODE=True
ENVIRONMENT=development

DATABASE_URL=postgresql+asyncpg://devuser:devpass@localhost:5432/erp_dev_db

REDIS_HOST=localhost
REDIS_PORT=6379
# REDIS_PASSWORD=your_local_redis_password_if_any

JWT_SECRET_KEY=your_super_secret_jwt_key_for_development_do_not_use_in_prod
# ... other variables ...
```

##### Secrets Management Integration

- Sensitive values (e.g., `DATABASE_URL` (with password), `JWT_SECRET_KEY`, `AWS_SECRET_ACCESS_KEY`) defined in the `Settings` model will have their actual values injected as environment variables in production/staging environments.
- This injection is managed by the secrets management system before the application starts. Pydantic Settings then reads these environment variables.

#### Configuration Variables

Key configuration variables include, but are not limited to:

- `DEBUG_MODE`
- `ENVIRONMENT`
- `DATABASE_URL`
- `REDIS_HOST`, `REDIS_PORT`, `REDIS_PASSWORD`, DB numbers for different uses
- `JWT_SECRET_KEY`, `JWT_ALGORITHM`, token lifetimes
- `CORS_ALLOWED_ORIGINS`
- `FILE_STORAGE_BACKEND` and associated cloud credentials/bucket names
- `SENTRY_DSN`
- External service API keys
- Rate limiting parameters, pagination sizes

#### Process & Workflow

- **Adding New Config:**
  1. Define the new setting with its type hint and a sensible default (if applicable) in `app/core/config.py:Settings`.
  2. Add the variable to `.env.example` with a comment.
  3. Developers update their local `.env` if needed.

- **Local Development:** Developers manage their local configuration via their `.env` file.

- **Testing:**
  - Automated tests will be written using the **Pytest** framework.
  - For most test scenarios, the application will load its configuration via Pydantic Settings using default values defined in `app/core/config.py:Settings` or from environment variables specifically set for the CI/test execution environment.
  - If a test requires specific configuration values that differ from the defaults or CI environment settings:
    - A dedicated `.env.test` file can be created and loaded by Pydantic Settings if the test environment is configured to prioritize it.
    - **Pytest fixtures** will be used to provide or override specific settings values for the duration of a test or a test module.

Example test fixture:
```python
# conftest.py or specific test file
import pytest
from app.core.config import Settings, settings as global_settings

@pytest.fixture
def override_debug_settings(monkeypatch):
    monkeypatch.setattr(global_settings, 'DEBUG_MODE', True)
    # Or, for a more isolated approach if settings are re-instantiated per test:
    # test_settings = Settings(DEBUG_MODE=True, _env_file=None) # Disable .env loading for this override
    # monkeypatch.setattr('app.module_using_settings.settings', test_settings)
    # yield
    # monkeypatch.undo() # If not using global settings modification for test scope
```

- **Staging/Production:** All configuration, especially secrets, is provided via environment variables injected by the deployment platform or secrets management system. **No `.env` file should be present in staging or production.**

- **Documentation:** The `app/core/config.py` file (with comments) and `.env.example` serve as the primary documentation for available configuration settings.

#### Security Considerations

- **Secrets MUST NOT be committed to Git** (neither in code nor in `.env` files, except `.env.example`).
- Use a secure method for managing and injecting secrets in staging/production.
- Regularly rotate secrets where possible/required.
- Limit access to production configuration and secrets.
- The `JWT_SECRET_KEY` and other cryptographic keys must be strong and unique per environment.

#### Tooling

- `pydantic-settings` library.
- Secrets Management tool (e.g., AWS Secrets Manager, HashiCorp Vault).
- Version Control (Git) for `app/core/config.py` and `.env.example`.

### 2.2 Secrets Management Strategy

#### Overview

- **Purpose**: To define the strategy for securely managing and accessing sensitive information (secrets) required by the FastAPI-based ERP application, ensuring they are protected throughout their lifecycle.
- **Scope**: Covers the definition of secrets, chosen storage solution (AWS Secrets Manager), access control, rotation policies, and integration with the application's configuration system (Pydantic Settings).
- **Chosen Technology**: **AWS Secrets Manager** as the primary secrets storage solution. Principles apply to alternatives like HashiCorp Vault or other cloud provider secret managers.

#### Core Principles

- **Centralized Secure Storage**: Store all application secrets in a dedicated, hardened secrets management system, not in version control, configuration files, or application code.
- **Least Privilege Access**: Grant applications, services, and users only the minimum necessary permissions to access specific secrets they require.
- **Encryption at Rest and in Transit**: Ensure secrets are encrypted both when stored within the secrets manager and when being transmitted to the application or authorized users. AWS Secrets Manager handles this by default (using AWS KMS).
- **Auditing**: Maintain comprehensive audit trails of all secret access, modifications, and management operations.
- **Rotation**: Implement automated or well-defined manual rotation policies for secrets to limit the window of exposure if a secret is compromised.
- **No Hardcoded Secrets**: Secrets must never be hardcoded.

#### Definition of Secrets

Secrets for the ERP application include, but are not limited to:

- **Database Credentials**: The full `DATABASE_URL` containing username and password for PostgreSQL.
- **`JWT_SECRET_KEY`**: The secret key used for signing and verifying JSON Web Tokens.
- **Redis Password**: If Redis instances are password-protected (`settings.REDIS_PASSWORD`).
- **Elasticsearch Credentials**: Username and password if Elasticsearch is secured (`settings.ELASTICSEARCH_USERNAME`, `settings.ELASTICSEARCH_PASSWORD`).
- **Cloud Provider Service Keys**:
  - `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` for accessing AWS services like S3.
  - Equivalent credentials for other cloud services if applicable.
- **External Third-Party API Keys**: Keys for payment gateways, email services, mapping services, tax calculation services, etc.
- **Internal Service-to-Service Credentials**: If applicable.
- **Cryptographic Keys**: Any other application-level encryption or signing keys.
- **Sentry DSN**: While not a "secret" in the same vein as a password, the Sentry DSN is sensitive and should be managed as configuration injected from a secure source.

#### AWS Secrets Manager Integration & Workflow

##### Storing Secrets in AWS Secrets Manager

- **Creation**: Secrets will be created and managed within AWS Secrets Manager via the AWS Console, CLI, or Infrastructure as Code (e.g., Terraform, CloudFormation).
- **Secret Structure**: Secrets can be stored as:
  - **Plaintext**: For single values like `JWT_SECRET_KEY`.
  - **JSON Key-Value Pairs**: For grouped credentials, e.g., a single secret named `erp/production/database` could store a JSON object like `{"DATABASE_URL": "postgresql+asyncpg://user:verysecretpass@host/db"}`.
- **Naming Convention**: A consistent naming convention will be used for secrets in AWS Secrets Manager to clearly identify their purpose and environment.
  - Format: `erp/{environment}/{service_or_component}/{secret_name}`
  - Examples:
    - `erp/production/postgresql/database_url`
    - `erp/staging/jwt/secret_key`
    - `erp/production/redis/password`
    - `erp/production/aws/s3_app_user_credentials`
    - `erp/production/external_services/payment_gateway_api_key`

##### Application Access to Secrets & Integration with Pydantic Settings

- **Primary Method: Injection as Environment Variables at Deployment/Startup.**
  1. **IAM Permissions:** The application's runtime environment will be granted fine-grained IAM permissions to read only the specific secrets it requires.
  2. **Secret Retrieval Process:** During the application's deployment or container startup sequence:
     - A script will authenticate to AWS using the instance/task IAM role.
     - This script will fetch the required secret values from AWS Secrets Manager.
     - If a secret is a JSON string containing multiple key-value pairs, the script will parse the JSON.
     - The retrieved secret values will be exported as environment variables for the FastAPI application process.
  3. **Consumption by Pydantic Settings:**
     - The FastAPI application's `pydantic-settings` configuration will automatically read these environment variables.
     - At application startup, the `Settings` class will populate its attributes with the secret values.

##### Example `Settings` Model Attributes for Secrets

```python
# app/core/config.py (relevant Pydantic Settings attributes)
class Settings(BaseSettings):
    # These are expected to be populated from environment variables,
    # which in turn are populated from AWS Secrets Manager in prod/staging.
    DATABASE_URL: PostgresDsn
    JWT_SECRET_KEY: str
    REDIS_PASSWORD: Optional[str] = None
    ELASTICSEARCH_PASSWORD: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None # If S3 user keys are used
    # ... other secret-dependent settings ...
```

#### Secret Rotation

- **Automated Rotation (AWS Secrets Manager Feature):**
  - For supported services like **AWS RDS database credentials**, AWS Secrets Manager's native rotation capabilities will be configured.
  - Secrets Manager will automatically rotate these credentials with the database and update the secret value.
- **Custom Rotation Lambda Functions:**
  - For other secrets, custom AWS Lambda functions will be developed to handle automated rotation if supported.
  - These Lambda functions will be scheduled and configured as custom rotation functions within AWS Secrets Manager.
- **Manual Rotation:**
  - For secrets where automated rotation is not feasible, a documented manual rotation procedure will be established.
  - Rotation frequency will be defined based on risk assessment.
- **Application Impact:**
  - Applications typically need to be restarted or redeployed to pick up rotated secret values.
  - Deployment strategies will facilitate this process with minimal downtime.

#### Local Development

- For local development, developers will use a local `.env` file to define values for secret-dependent settings.
- **These local `.env` files must contain non-production, development-only values and must never be committed to version control.**
- Direct developer access to production or staging secrets in AWS Secrets Manager will be highly restricted.

#### Security Best Practices & Auditing

- **IAM Least Privilege:** Ensure IAM roles/users have only the necessary permissions on specific secrets.
- **Encryption:** Utilize AWS KMS for encrypting secrets within Secrets Manager.
- **Audit Logging:** AWS CloudTrail will be enabled and configured to log all API calls to AWS Secrets Manager.
- **VPC Endpoints:** Configure VPC interface endpoints for AWS Secrets Manager in AWS environments.
- **Regular Review:** Periodically review IAM permissions and secrets.

#### Tooling

- **Primary:** AWS Secrets Manager.
- **Supporting:** AWS IAM (for access control), AWS KMS (for encryption), AWS CloudTrail (for auditing), AWS CLI / SDKs (for scripted access and retrieval during deployment).

### 2.3 API Strategy

### 2.4 Validation Strategy

## 3. Data Layer

### 3.1 Database PostgreSQL Strategy

### 3.2 Migration and DB Management Strategy

### 3.3 Cache Redis

### 3.4 File Storage

## 4. Application Services

### 4.1 Asynchronous Celery

### 4.2 Email Service Integration

### 4.3 Search Strategy

### 4.4 Real-time Strategy

### 4.5 Feature Flags Strategy

### 4.6 Localization Strategy

### 4.7 Logging Strategy

## 5. Development & Operations

### 5.1 Testing Strategy TDD

### 5.2 Security Strategy

### 5.3 Monitoring Strategy

### 5.4 Deployment Strategy and CI/CD 