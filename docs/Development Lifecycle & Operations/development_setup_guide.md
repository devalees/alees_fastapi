# Local Development Environment Setup Guide (FastAPI Edition)

## 1. Overview

- **Purpose**: To provide step-by-step instructions for developers to set up the FastAPI-based ERP backend project and its dependencies on their local machine for development and testing.
- **Goal**: Enable developers to quickly get a working, consistent development environment running that mirrors the core technologies used in staging/production where feasible (PostgreSQL, Redis, Celery, Elasticsearch).
- **Primary Method**: Utilize **Docker** and **Docker Compose** to orchestrate required services and the application container.

## 2. Prerequisites

- **Git**: Must be installed ([https://github.com/devalees/alees_fastapi.git](https://git-scm.com/)).
- **Docker & Docker Compose**: Must be installed and running ([https://www.docker.com/products/docker-desktop/](https://www.docker.com/products/docker-desktop/)). Ensure sufficient resources (RAM/CPU) are allocated to Docker Desktop.
- **Python (Optional, for local tools/IDE integration):** A recent version compatible with the project (e.g., Python 3.10+) installed locally can be helpful for IDE features (linting, type checking outside the container) and running some standalone scripts, but primary development and execution occur _inside_ the Docker container.
- **Code Editor/IDE**: VS Code (with Dev Containers extension recommended), PyCharm Professional (with Docker integration), or similar.
- **(Optional) `make`**: A `Makefile` can be provided in the project root to simplify common Docker Compose commands (e.g., `make build`, `make up`, `make logs`, `make test`).

## 3. Initial Setup Steps

1.  **Clone Repository:**

    ```bash
    git clone <your_repository_url> erp_fastapi_project
    cd erp_fastapi_project
    ```

2.  **Environment Configuration (`.env` file):**

    - Copy the example environment file: `cp .env.example .env`
    - **Review and Edit `.env`:** Open the `.env` file in your editor.
    - Fill in necessary values, especially:
      - `DATABASE_URL`: Verify it matches the PostgreSQL service credentials and port defined in `docker-compose.yml` (e.g., `postgresql+asyncpg://erp_user:erp_pass@localhost:5432/erp_dev_db`).
      - `REDIS_HOST`, `REDIS_PORT`, `REDIS_PASSWORD` (if any for local Redis).
      - `JWT_SECRET_KEY`: Generate a strong, random secret key (e.g., using `openssl rand -hex 32`). **Do not use the example key from `.env.example` for anything other than initial testing if it's weak.**
      - Other settings from `app/core/config.py:Settings` that might need local overrides (e.g., `DEBUG_MODE=True`, `ENVIRONMENT=development`).
    - **Important:** The `.env` file is ignored by Git (via `.gitignore`) and must **never** be committed with actual secrets.

3.  **Build Docker Images:**

    - Build the application image and any other custom images defined in `docker-compose.yml`.
    - Command: `docker-compose build`
      - (Or `make build` if a Makefile target exists)

4.  **Start Background Services:**

    - Start the background services (PostgreSQL, Redis, optionally Elasticsearch for local search dev) defined in `docker-compose.yml`.
    - Command: `docker-compose up -d postgres redis es01` (Replace service names with actual names from your `docker-compose.yml`. `es01` is a common name for a single-node Elasticsearch dev instance).
    - Wait a few seconds for them to initialize fully. Check logs with `docker-compose logs postgres redis es01`.

5.  **Run Initial Database Migrations (Alembic):**

    - Run Alembic migrations _inside_ the application container to set up the database schema. The `api` service (or whatever you name your FastAPI app service in `docker-compose.yml`) will need access to the database.
    - Command: `docker-compose run --rm api alembic upgrade head`
      - (Or `make migrate` if a Makefile target exists)

6.  **Create Initial User/Seed Data (Optional but Recommended):**

    - If you have scripts or custom Alembic data migrations to create an initial admin user or seed essential lookup data (e.g., default roles, organization types):
    - Command: `docker-compose run --rm api python -m app.scripts.seed_initial_data` (if you create such a script)
      - Or, if it's an Alembic data migration, it would have been run in the previous step.
    - To create a superuser, you might have a CLI command exposed via Typer/Click within your app, callable like: `docker-compose run --rm api python -m app.cli users create-superuser --username admin --email admin@example.com --password changeme`

7.  **Start Development Server (FastAPI with Uvicorn):**
    - Start the main FastAPI application server (running inside the `api` container). This will typically run Uvicorn with live reloading enabled for development.
    - Command: `docker-compose up api`
      - (Or `make up-api` or just `make up` if it includes the API service)
    - The `docker-compose.yml` for the `api` service should specify a command like:
      `command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir /app/app`
    - Access the application at `http://localhost:8000` (or the mapped port). The OpenAPI docs will typically be at `http://localhost:8000/docs` or `/redoc`.

## 4. Common Development Tasks (Executed via `docker-compose run --rm api ...` or `make ...`)

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

  1.  Make changes to your SQLAlchemy models in `app/.../models.py`.
  2.  Generate a new revision:
      ```bash
      docker-compose run --rm api alembic revision -m "add_new_field_to_products"
      # For autogenerate (review carefully!):
      docker-compose run --rm api alembic revision --autogenerate -m "auto_add_new_field_to_products"
      ```
  3.  **Crucially, inspect and edit the generated migration script** in `alembic/versions/`.
  4.  Apply the migration locally:
      ```bash
      docker-compose run --rm api alembic upgrade head
      ```

- **Running Linters/Formatters (if not fully integrated into IDE/pre-commit hooks):**

  ```bash
  docker-compose run --rm api ruff check .
  docker-compose run --rm api ruff format .
  docker-compose run --rm api mypy .
  # Or make targets: make lint, make format
  ```

- **Running Celery Worker (Manual, for debugging specific tasks):**

  - Ensure Celery and its broker (Redis) are configured in `docker-compose.yml` and your Pydantic settings.
  - Start a Celery worker process:
    ```bash
    docker-compose run --rm celery_worker celery -A app.core.celery_config.celery_app worker -l INFO -P eventlet # Or gevent, or default solo pool
    # Ensure your Celery app instance is correctly referenced (e.g., app.core.celery_config.celery_app)
    # The celery_worker service should be defined in docker-compose.yml, sharing the same codebase.
    ```
    (Alternatively, add `celery_worker` as a service in `docker-compose.yml` and use `docker-compose up celery_worker`)

- **Running Celery Beat (Manual, for debugging scheduled tasks):**

  - Ensure Celery Beat and its custom database scheduler are configured.
  - Start the Celery Beat process:
    ```bash
    docker-compose run --rm celery_beat celery -A app.core.celery_config.celery_app beat -l INFO --scheduler app.tasks.db_scheduler.DatabaseScheduler # Path to your custom scheduler
    ```
    (Alternatively, add `celery_beat` as a service in `docker-compose.yml` and use `docker-compose up celery_beat`)
  - _Note: For general development where async tasking isn't the focus, you might not run Celery workers/beat continuously. Set `task_always_eager=True` (if Celery supports this well with async tasks) in a local dev setting for synchronous execution if needed for simplicity, but this bypasses actual queueing._

- **Accessing Python Shell/REPL (IPython inside container):**

  ```bash
  docker-compose run --rm api ipython
  # Inside IPython, you can import your app modules, services, etc.
  ```

- **Stopping Services:**

  ```bash
  docker-compose down # Stops and removes containers, networks, and default volumes
  # or
  docker-compose stop # Stops containers without removing them
  ```

  To remove named volumes (like PostgreSQL data): `docker-compose down -v` (Use with caution, as it deletes data).

- **Accessing Database (e.g., psql or GUI client):**

  - Connect to `localhost` on the port mapped for PostgreSQL in `docker-compose.yml` (e.g., `5432`).
  - Use credentials from your `.env` file (`DATABASE_URL`).
  - Example `psql`: `psql postgresql://erp_user:erp_pass@localhost:5432/erp_dev_db`

- **Accessing Redis (e.g., redis-cli):**
  - Connect to `localhost` on the port mapped for Redis (e.g., `6379`).
  - `redis-cli -h localhost -p 6379` (add `-a <password>` if Redis is password-protected locally).

## 5. IDE Integration (VS Code Dev Containers Example)

- If using VS Code, setting up a `.devcontainer/devcontainer.json` configuration allows you to develop directly _inside_ the running `api` Docker container.
- This provides a consistent environment with all tools (Python, linters, formatters, test runners) available directly, matching the container's setup.
- The `devcontainer.json` would specify the Docker Compose service to use (e.g., `api`), extensions to install, and post-create commands.

## 6. Adding New Features or Components

When extending the application with new features or services:

1. **Creating a New Feature Module:**
   - Follow the feature-based structure: create a new directory under `app/features/` (e.g., `app/features/orders/`)
   - Create the standard component files:
     ```
     app/features/new_feature/
     ├── __init__.py
     ├── router.py       # FastAPI router definition
     ├── schemas.py      # Pydantic models for API I/O
     ├── models.py       # SQLAlchemy ORM models
     ├── service.py      # Business logic 
     └── exceptions.py   # Feature-specific exceptions
     ```
   - Register the router in `app/main.py` with appropriate prefixes

2. **Implementing Database Models:**
   - Extend `BaseModel` from `app.core.base_models` for consistent ID and timestamp fields
   - After defining models, generate and review migrations with Alembic

3. **Adding Background Tasks:**
   - Create task functions in a `tasks.py` file within your feature module
   - Register the module in Celery's `autodiscover_tasks` if not already included

4. **Writing Tests:**
   - Follow the established test structure with unit/integration/api directories
   - Make use of test factories (in `tests/factories/`) for consistent test data

## 7. Debugging Tips

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

## 8. Troubleshooting Tips

- **Ensure Docker Desktop is running** and has sufficient resources allocated (CPU, Memory).
- **Verify `.env` file:** Ensure variables are correctly set and match `docker-compose.yml` service definitions (e.g., database host set to the service name like `postgres` if accessing from another container, or `localhost` if accessing from host via mapped port).
- **Check Container Logs:** If services fail to start or behave unexpectedly, check logs: `docker-compose logs <service_name>` (e.g., `docker-compose logs api`, `docker-compose logs postgres`).
- **Rebuild Images:** If you change `Dockerfile` or installed dependencies: `docker-compose build --no-cache <service_name>`.
- **Clean Up Docker Resources:** Occasionally, prune unused Docker images, containers, volumes, and networks: `docker system prune -a --volumes`.
- **Port Conflicts:** Ensure ports mapped in `docker-compose.yml` (e.g., 8000, 5432, 6379) are not already in use on your host machine.
- **Permission Issues:** Some systems may encounter permission problems with mounted volumes. Solutions include:
  - Setting appropriate user permissions in the Dockerfile
  - Using Docker Compose's `user` option to match your host UID/GID
  - Adjusting volume mount permissions in Docker settings

## 9. Best Practices for Development

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
