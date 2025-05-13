# Testing Strategy (TDD with Pytest for FastAPI)

## 1. Overview

- **Purpose**: To define the strategy, methodologies, tools, and scope for testing the FastAPI-based ERP backend application, ensuring its correctness, reliability, performance, and security by primarily following a **Test-Driven Development (TDD)** approach.
- **Scope**: Covers unit testing, integration testing, and API testing practices throughout the development lifecycle, emphasizing writing tests before or concurrently with implementation code.
- **Goal**: High test coverage driven by requirements, early defect detection and prevention, confidence in deployments, a maintainable test suite, and improved design through a focus on testability.
- **Primary Framework**: **Pytest** (with `pytest-asyncio` for async code and FastAPI's `TestClient`).

## 2. Testing Philosophy & Principles

- **Test-Driven Development (TDD) Focus**: Development will primarily follow the Red-Green-Refactor cycle:
  1.  **Red:** Write a failing test for a small piece of desired functionality based on requirements/specifications.
  2.  **Green:** Write the _minimum_ amount of production code necessary to make the test pass.
  3.  **Refactor:** Improve the production code (and potentially the test code) for clarity, efficiency, and design quality, ensuring tests still pass.
- **Testing Pyramid/Trophy**: TDD applies at all levels, with a balanced distribution:
  - **Unit Tests (Large Base):** Most TDD cycles occur here. Test small, isolated units (functions, Pydantic model validators, individual service logic units).
  - **Integration Tests (Middle Layer):** Test the interaction between a few components (e.g., service interacting with the database, router calling a service).
  - **API / End-to-End Tests (Smaller Top, focused on API contract):** Test the full request-response cycle for API endpoints, verifying behavior as seen by an API consumer. These often drive the development of lower-level unit/integration tests.
- **Test Early, Test Often**: Write tests _before or concurrently with_ code. Run tests frequently locally and automatically in CI.
- **Automation**: Automate test execution via Continuous Integration (CI).
- **Clarity & Maintainability**: Tests act as executable specifications and documentation. They must be readable, well-named, and maintainable. Use clear assertions and descriptive failure messages.
- **Isolation**: Design tests for isolation. Use Pytest fixtures for setup/teardown and mocking (via `pytest-mock`) for external dependencies or components not under test in unit tests.
- **Coverage as an Outcome**: High test coverage is a _result_ of practicing TDD thoroughly and testing behaviors, not the primary goal itself. Focus on testing requirements, critical paths, and edge cases.

## 3. Testing Framework & Tools

- **Core Test Runner:** **Pytest** (`pytest`).
- **Async Testing:** **`pytest-asyncio`** (for testing `async def` functions).
- **API Client (for API tests):** FastAPI's `TestClient` (which uses `httpx`).
- **Test Data Generation:** **`factory-boy`** (with a SQLAlchemy adapter if models are complex, or direct Pydantic model instantiation for simpler data).
  - Consider **`pytest-factoryboy`** for easier fixture generation from factories.
- **Mocking:** Python's `unittest.mock` (via `pytest-mock`'s `mocker` fixture).
- **Asynchronous Task Testing (Celery):**
  - Celery's testing utilities (e.g., `task_always_eager=True` in test settings).
  - **`pytest-celery`** can provide useful fixtures and utilities if needed for more complex Celery testing scenarios.
- **Time Manipulation:** `freezegun` (for testing time-sensitive logic).
- **Database Interaction (SQLAlchemy):** Test database setup will be managed by Pytest fixtures, typically creating tables via Alembic or `Base.metadata.create_all()` for each test session or module. (Details in `testing_environment_setup.md`).
- **Coverage:** `pytest-cov`.
- **(Future Consideration) Property-Based Testing:** `hypothesis` (can complement TDD by exploring a wider range of inputs and edge cases).
- **(Separate) Performance Testing:** `locust` (for load testing APIs).
- **(Separate) Security Testing:** SAST (`bandit`), DAST (OWASP ZAP) - integrated into CI or run periodically.

## 4. Types of Tests & TDD Workflow

### 4.1 Unit Tests

- **TDD Cycle:**
  1.  Identify a small unit of behavior (e.g., a specific Pydantic validator, a calculation in a service function, a utility function).
  2.  Write a Pytest test function (`async def test_...` if testing async code) asserting the expected outcome or raised exception. Use `mocker` to isolate from external dependencies (DB, network calls, other services). Run it; it should fail (Red).
  3.  Implement the minimal code in the Pydantic model, service function, or utility to make the test pass (Green).
  4.  Refactor the implementation and test code. Rerun tests (Green).
- **Scope:** Pydantic model validation/transformation, individual service functions (business logic), utility functions, core components (`app/core/`).

### 4.2 Integration Tests

- **TDD Cycle:**
  1.  Identify an interaction between components (e.g., a service function correctly interacting with the SQLAlchemy ORM and test database, a router correctly calling a service and handling its response/exceptions).
  2.  Write an integration test (often `async def`, using a test database session fixture). Set up initial state (e.g., using factories or direct DB inserts), perform the action, and assert the expected outcome on interacting components (e.g., database state changed correctly, correct data returned). Run it; it should fail (Red).
  3.  Implement the interaction logic. For these tests, actual database interaction is usually desired (not mocked). Mock only true external third-party services. Make the test pass (Green).
  4.  Refactor. Rerun tests (Green).
- **Scope:** Service layer functions interacting with the database, Celery tasks interacting with the database or other internal services, interactions between different internal services/modules.

### 4.3 API Tests (Primary focus for behavior validation)

- **TDD Cycle (BDD Influence):**
  1.  Define the desired API behavior for an endpoint based on a user story or API specification (e.g., "POST to `/api/v1/products/` with valid data should return 201 and the created product").
  2.  Write an API test using FastAPI's `TestClient`. Make the HTTP request, provide input data (as dicts/JSON), and assert the expected HTTP status code, response headers, and JSON response body structure/content. Run it; it should fail (Red).
  3.  Implement the minimal FastAPI path operation function, Pydantic schemas, and underlying service logic required to make the API test pass (Green). This often involves driving out lower-level unit/integration tests via TDD for the services and models involved.
  4.  Refactor the API implementation (router, schemas, services) and the test. Rerun tests (Green).
- **Scope:** All API endpoints: CRUD operations, authentication/authorization flows, input validation (Pydantic errors), error handling (custom exception handlers), filtering/sorting/pagination, rate limiting responses, security headers.

## 5. Test Execution & CI/CD

- **Local Execution:** Developers run `pytest` (or specific test files/markers) frequently during TDD.
- **Continuous Integration (CI):** (As defined in `deployment_strategy_and_ci_cd.md (FastAPI Edition)`)
  - Runs the full Pytest suite automatically.
  - Includes linting, static analysis, type checking, dependency scanning.
  - Generates coverage reports. Build fails if tests fail or quality gates (e.g., coverage drop) are not met.

## 6. Test Data Management

- **Primary Tool:** **`factory-boy`** (potentially with an async SQLAlchemy adapter or careful session management if factories create DB records). Define factories early.
  - Alternatively, for simpler scenarios or API tests, Pydantic models can be directly instantiated with test data.
- **Data Creation:** Create only necessary data within each test function or fixture.
- **Database State:** Each test (or test class/module) should run against a clean, known database state. Test database setup/teardown is managed by fixtures (see `testing_environment_setup.md`).

## 7. Test Organization (`tests/` directory)

- Mirror the `app/` directory structure within `tests/` (e.g., `tests/features/users/test_router.py`, `tests/core/test_config.py`).
- Use descriptive filenames (`test_*.py` or `*_test.py`) and test function names (`test_behavior_under_condition_expects_outcome`).
- Use Pytest markers for categorization (e.g., `@pytest.mark.unit`, `@pytest.mark.integration`, `@pytest.mark.api`, `@pytest.mark.slow`).

## 8. Responsibilities

- **Developers:** Primarily responsible for writing unit, integration, and API tests following TDD. Maintain tests as code evolves. Ensure high quality and coverage for the code they write.
- **All Team Members (including AI agents generating code):** Adhere to the TDD process. Test code must be reviewed alongside application code.
