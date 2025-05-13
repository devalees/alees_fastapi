
├── alembic/                    # Alembic migration scripts and configuration
│   ├── versions/
│   └── env.py
├── app/                        # Main application source code directory
│   ├── __init__.py
│   │
│   ├── core/                   # Core infrastructure, configurations, base classes (Layer)
│   │   ├── __init__.py
│   │   ├── config.py           # Application settings (Pydantic Settings)
│   │   ├── db.py               # Database session management, engine setup
│   │   ├── security.py         # Password hashing, JWT utilities
│   │   ├── dependencies.py     # Common FastAPI dependencies
│   │   └── base_models.py      # Base ORM model with common fields
│   │
│   ├── common_services/        # Shared business logic or utilities used by multiple features
│   │   ├── __init__.py
│   │   ├── notifications/
│   │   │   ├── __init__.py
│   │   │   ├── service.py
│   │   │   └── schemas.py
│   │   ├── audit_log/
│   │   │   ├── __init__.py
│   │   │   ├── service.py
│   │   │   └── models.py
│   │   └── ...
│   │
│   ├── features/               # Feature-specific modules
│   │   ├── __init__.py
│   │   ├── users/
│   │   │   ├── __init__.py
│   │   │   ├── router.py
│   │   │   ├── schemas.py
│   │   │   ├── service.py
│   │   │   ├── models.py
│   │   │   └── exceptions.py
│   │   ├── products/
│   │   │   └── ...
│   │   ├── organizations/
│   │   │   └── ...
│   │   ├── settings_management/ # Module for app-specific settings
│   │   │   └── ...
│   │   └── ...
│   │
│   ├── main.py                 # Main FastAPI application instance
│   └── py.typed                # Marker file for mypy PEP 561
│
├── tests/                      # Root tests directory
│   ├── __init__.py
│   │
│   ├── core/                   # Tests for app.core modules
│   │   ├── __init__.py
│   │   ├── unit/               # Unit tests for core components
│   │   │   ├── __init__.py
│   │   │   └── test_config.py
│   │   │   └── test_security_utils.py
│   │   └── integration/        # Integration tests for core components (e.g., db session)
│   │       └── __init__.py
│   │
│   ├── common_services/        # Tests for app.common_services
│   │   ├── __init__.py
│   │   ├── notifications/
│   │   │   ├── __init__.py
│   │   │   ├── unit/
│   │   │   │   └── test_notification_service_logic.py
│   │   │   └── integration/
│   │   │       └── test_notification_service_with_broker.py # (if applicable)
│   │   └── audit_log/
│   │       └── ...
│   │
│   ├── features/               # Tests for app.features modules
│   │   ├── __init__.py
│   │   ├── users/              # Tests for the 'users' feature
│   │   │   ├── __init__.py
│   │   │   ├── unit/           # Unit tests for user services, schemas, utilities
│   │   │   │   ├── __init__.py
│   │   │   │   └── test_user_schemas.py
│   │   │   │   └── test_user_service_logic.py
│   │   │   ├── integration/    # Integration tests for user services interacting with DB
│   │   │   │   ├── __init__.py
│   │   │   │   └── test_user_service_db.py
│   │   │   └── api/            # API tests (end-to-end for this feature's API)
│   │   │       ├── __init__.py
│   │   │       └── test_user_router.py # Tests HTTP requests to user endpoints
│   │   ├── products/
│   │   │   ├── __init__.py
│   │   │   ├── unit/
│   │   │   ├── integration/
│   │   │   └── api/
│   │   └── ...                 # Other features follow the same unit/integration/api structure
│   │
│   ├── conftest.py             # Project-level Pytest fixtures (e.g., db_session, test_client)
│   └── factories/              # Central place for factory-boy factories (optional, can also be per-feature)
│       ├── __init__.py
│       └── user_factories.py
│       └── product_factories.py
│
├── requirements/               # Dependency management
│   ├── base.txt
│   ├── dev.txt
│   ├── test.txt
│   └── prod.txt
|
├── .env.example
├── .gitignore
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── README.md
└── ...
