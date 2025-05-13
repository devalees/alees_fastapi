
# Configuration Management Strategy (FastAPI Edition)

## 1. Overview

- **Purpose**: To define the strategy for managing application configuration settings across different environments (development, testing, staging, production) in a consistent, secure, and maintainable manner for the FastAPI-based ERP system.
- **Scope**: Covers management of application settings, environment variables, and sensitive credentials (secrets) integration.
- **Goal**: Ensure the application behaves correctly in each environment, secrets are handled securely, configuration is easy to manage and deploy, and environment differences are clearly defined using Pydantic Settings.

## 2. Core Principles

- **Environment Parity (Strive for):** Keep development, staging, and production environments as similar as possible regarding configuration structure, varying only environment-specific values.
- **Configuration in Environment:** Store environment-specific configuration (especially secrets, hostnames, resource locators) in the **environment**, not in version-controlled code.
- **Explicit Configuration:** Rely on explicitly defined settings. Pydantic Settings enforces this by requiring fields to be declared.
- **Security:** Treat all sensitive configuration values (passwords, API keys, cryptographic keys) as secrets, managed via a secure mechanism (see `secrets_management_strategy.md`).
- **Consistency:** Use a consistent method (Pydantic Settings instance) for accessing configuration values throughout the application code.
- **Immutability (Ideal):** Configuration ideally doesn't change frequently after deployment without a new code release or explicit configuration update process impacting the environment.

## 3. Configuration Layers & Tools

### 3.1. Pydantic Settings (`app/core/config.py`)

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

      # Construct full URLs from components (example, can also take full URLs directly)
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

      # Add other application-specific settings here...
      # e.g., FEATURE_FLAG_XYZ_ENABLED: bool = False

      model_config = SettingsConfigDict(
          env_file=".env",
          env_file_encoding='utf-8',
          extra='ignore', # Ignore extra env vars not defined in the model
          case_sensitive=False # Environment variables are typically case-insensitive
      )

  settings = Settings() # Single, importable instance
  ```

- **Loading Priority:** `pydantic-settings` loads configuration from:
  1.  Arguments passed during `Settings` class initialization (not typical for global settings).
  2.  Environment variables (case-insensitive by default).
  3.  Variables loaded from the `.env` file specified in `env_file`.
  4.  Variables loaded from secrets files (if `secrets_dir` is configured).
  5.  Default values defined in the `Settings` model.
- **Usage:** Import the `settings` instance: `from app.core.config import settings`. Access values like `settings.DATABASE_URL`.

### 3.2. Environment Variables & `.env` File

- **Primary Mechanism for Overrides:** Environment variables are the primary method for injecting environment-specific configuration and secrets into the application, overriding defaults or `.env` values.
- **`.env` File:**

  - Used _only_ for local development.
  - Contains environment variables, including secrets for local development instances (e.g., a development `JWT_SECRET_KEY`, local `DATABASE_URL`).
  - **Must be added to `.gitignore`**.
  - A `.env.example` file **must** be committed to Git, showing all required variables without their actual values. This serves as documentation for operators and developers.

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

### 3.3. Secrets Management Integration

- Sensitive values (e.g., `DATABASE_URL` (with password), `JWT_SECRET_KEY`, `AWS_SECRET_ACCESS_KEY`) defined in the `Settings` model will have their actual values injected as environment variables in production/staging environments.
- This injection is managed by the secrets management system (see `secrets_management_strategy.md`) before the application starts. Pydantic Settings then reads these environment variables.

## 4. Configuration Variables (Examples)

Key configuration variables include, but are not limited to:

- `DEBUG_MODE`
- `ENVIRONMENT`
- `DATABASE_URL`
- `REDIS_HOST`, `REDIS_PORT`, `REDIS_PASSWORD`, DB numbers for different uses
- `JWT_SECRET_KEY`, `JWT_ALGORITHM`, token lifetimes
- `CORS_ALLOWED_ORIGINS`
- `FILE_STORAGE_BACKEND` and associated cloud credentials/bucket names (cloud credentials typically managed by secrets manager)
- `SENTRY_DSN`
- External service API keys (managed by secrets manager)
- Rate limiting parameters, pagination sizes.

## 5. Process & Workflow

- **Adding New Config:**
  1.  Define the new setting with its type hint and a sensible default (if applicable) in `app/core/config.py:Settings`.
  2.  Add the variable to `.env.example` with a comment.
  3.  Developers update their local `.env` if needed.
- **Local Development:** Developers manage their local configuration via their `.env` file.
- **Testing:**

  - Automated tests will be written using the **Pytest** framework.
  - For most test scenarios, the application will load its configuration via Pydantic Settings using default values defined in `app/core/config.py:Settings` or from environment variables specifically set for the CI/test execution environment.
  - If a test requires specific configuration values that differ from the defaults or CI environment settings:

    - A dedicated `.env.test` file can be created and loaded by Pydantic Settings if the test environment is configured to prioritize it. This method is useful for setting a baseline test configuration.
    - **Pytest fixtures** will be used to provide or override specific settings values for the duration of a test or a test module. This is achieved by patching the `app.core.config.settings` object or by providing a modified `Settings` instance via a fixture.

      ```python
      # conftest.py or specific test file (Conceptual Example)
      # import pytest
      # from app.core.config import Settings, settings as global_settings

      # @pytest.fixture
      # def override_debug_settings(monkeypatch):
      #     monkeypatch.setattr(global_settings, 'DEBUG_MODE', True)
      #     # Or, for a more isolated approach if settings are re-instantiated per test:
      #     # test_settings = Settings(DEBUG_MODE=True, _env_file=None) # Disable .env loading for this override
      #     # monkeypatch.setattr('app.module_using_settings.settings', test_settings)
      #     # yield
      #     # monkeypatch.undo() # If not using global settings modification for test scope
      ```

  - Tests **must not** rely on a developer's local `.env` file for their correct execution. Test environments must be self-contained and reproducible.
  - Secrets or sensitive API keys required for tests (e.g., for testing integrations with sandboxed external services) will be provided as environment variables within the secure CI/test environment, not hardcoded in tests or test configuration files.

- **Staging/Production:** All configuration, especially secrets, is provided via environment variables injected by the deployment platform or secrets management system. **No `.env` file should be present in staging or production.**
- **Documentation:** The `app/core/config.py` file (with comments) and `.env.example` serve as the primary documentation for available configuration settings.

## 6. Security Considerations

- **Secrets MUST NOT be committed to Git** (neither in code nor in `.env` files, except `.env.example`).
- Use a secure method for managing and injecting secrets in staging/production (see `secrets_management_strategy.md`).
- Regularly rotate secrets where possible/required.
- Limit access to production configuration and secrets.
- The `JWT_SECRET_KEY` and other cryptographic keys must be strong and unique per environment.

## 7. Tooling

- `pydantic-settings` library.
- Secrets Management tool (e.g., AWS Secrets Manager, HashiCorp Vault).
- Version Control (Git) for `app/core/config.py` and `.env.example`.
