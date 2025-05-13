# Testing Documentation

This directory contains tests for the FastAPI application, following the Test-Driven Development (TDD) approach as outlined in `docs/Development Lifecycle & Operations/testing_strategy_tdd.md`.

## Test Structure

Tests are organized by feature, following a structure that mirrors the application structure:

```
tests/
├── conftest.py             # Common pytest fixtures
└── features/               # Feature-based test organization
    └── health/             # Health check endpoints
        └── api/            # API tests for health endpoints
            └── test_health_router.py  # Tests for health API endpoints
```

## Running Tests

### With Docker (Recommended)

Use the provided script to run tests with Docker:

```bash
./scripts/run-tests.sh
```

This script:
1. Stops any existing containers
2. Starts PostgreSQL and Redis services
3. Creates the test database
4. Runs the tests
5. Cleans up containers when done

### Manually with Docker Compose

If you need more control, you can run the tests manually:

```bash
# Start required services
docker-compose up -d postgres redis

# Wait for services to be ready (important!)
sleep 5

# Run the tests
docker-compose run --rm test
```

## Test Database Setup

The test environment uses:
- A dedicated PostgreSQL database (`erp_test_db`) for testing
- A Redis instance for caching
- Proper transaction isolation for tests

## Current Test Coverage

- `/api/v1/healthz/live` endpoint - Basic health check 