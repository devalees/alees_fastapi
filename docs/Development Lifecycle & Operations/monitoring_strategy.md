
# Monitoring & Observability Strategy (FastAPI Edition)

## 1. Overview
    * Purpose: To define the strategy for monitoring the health, performance, and behavior of the FastAPI-based ERP backend application and its supporting infrastructure.
    * Scope: Covers application instrumentation (metrics, logging, tracing, error tracking), health checks, and integration with a chosen monitoring stack.
    * Goal: Achieve comprehensive observability into production and staging environments for rapid issue detection, diagnosis, and performance optimization.
    * Approach: Instrument the FastAPI application to expose data and integrate with external monitoring tools.

## 2. Core Principles
    * External Tooling, Three Pillars (Metrics, Logs, Traces), Actionable Data, Automation, Contextualization.

## 3. Chosen Monitoring Stack (Adaptable - Strategic Overview)
    * Metrics: **Prometheus**
    * Visualization: **Grafana**
    * Log Aggregation: **Loki** (or ELK/EFK)
    * Log Agent: **Promtail** (or Fluentd/Filebeat)
    * Alerting: **Alertmanager**
    * Error Tracking: **Sentry**

## 4. Application Instrumentation (FastAPI - Strategic Overview)
    * **4.1. Metrics Exposure:** `starlette-prometheus` or manual `prometheus-client`.
    * **4.2. Structured Logging:** Python `logging` with JSON output. Context injection via middleware.
    * **4.3. Error Tracking (Sentry):** `sentry-sdk[fastapi]` with integrations.
    * **4.4. Distributed Tracing (OpenTelemetry - Future):** For advanced diagnostics.
    * **4.5. Health Check Endpoints:** `/healthz/live` and `/healthz/ready`.

## 5. Alerting Strategy (Strategic Overview)
    * Alertmanager (from Prometheus metrics) and Sentry alerts.
    * Focus on error rates, latency, resource saturation, queue lengths, critical service availability, health check failures.

## 6. Dashboards (Grafana - Strategic Overview)
    * Visualize key metrics: FastAPI app overview, DB performance, Celery, Redis, Elasticsearch, Infrastructure, Business Metrics.

## 7. Testing (Pytest - Strategic Overview)
    * Verify `/metrics` endpoint, log format/context, Sentry error reporting, health check responses.

## 8. General Setup Implementation Details (Monitoring Components in FastAPI)

    This section details the setup of core monitoring components within the FastAPI application.

    ### 8.1. Library Installation (Confirm in `requirements/base.txt` or `requirements/prod.txt`)
    *   `starlette-prometheus>=0.9.0,<0.10.0` (or latest stable)
    *   `prometheus-client>=0.17.0,<0.18.0`
    *   `sentry-sdk[fastapi]>=1.30.0,<2.0.0` (or latest stable)
    *   `python-json-logger>=2.0.0,<2.1.0`

    ### 8.2. Prometheus Metrics Setup (`app/main.py` and Custom Metrics)
    *   **8.2.1. Middleware Integration (`app/main.py`):**
        *   Integrate `starlette-prometheus` to expose a `/metrics` endpoint with default HTTP request metrics.
            ```python
            # app/main.py
            from fastapi import FastAPI
            from starlette_prometheus import metrics, PrometheusMiddleware
            from app.core.config import settings # Your Pydantic settings
            # ... other app setup ...

            app = FastAPI(
                title=settings.APP_NAME,
                # ...
            )

            # Add Prometheus middleware
            # Use an app_name that is valid for Prometheus labels (e.g., no spaces)
            prometheus_app_name = settings.APP_NAME.replace(" ", "_").lower()
            app.add_middleware(PrometheusMiddleware, app_name=prometheus_app_name)
            app.add_route("/metrics", metrics, include_in_schema=False) # Exposes the /metrics endpoint

            # ... rest of app setup ...
            ```
    *   **8.2.2. Pydantic Settings (`app/core/config.py`):**
        *   No specific settings required for basic `starlette-prometheus` integration beyond `APP_NAME`.
    *   **8.2.3. Custom Metrics Definition (Example in `app/core/metrics.py`):**
        *   Define custom business or application-level metrics using `prometheus-client`.
            ```python
            # app/core/metrics.py (or in relevant feature modules)
            from prometheus_client import Counter, Histogram, Gauge

            # Example: Counter for created entities
            ENTITIES_CREATED_COUNTER = Counter(
                "erp_entities_created_total",
                "Total number of specific entities created",
                ["entity_type", "organization_id"] # Example labels
            )

            # Example: Histogram for service function duration
            SERVICE_FUNCTION_DURATION_SECONDS = Histogram(
                "erp_service_function_duration_seconds",
                "Histogram of service function execution time",
                ["service_name", "function_name"]
            )

            # Example: Gauge for active WebSocket connections (if tracked)
            # ACTIVE_WEBSOCKET_CONNECTIONS_GAUGE = Gauge(
            #     "erp_active_websocket_connections",
            #     "Number of active WebSocket connections"
            # )

            # These metrics are automatically registered with the default Prometheus registry
            # when defined at the module level.
            ```
        *   These custom metrics are then incremented/observed within your application code.

    ### 8.3. Sentry Initialization and Configuration (`app/main.py`)
    *   **8.3.1. SDK Initialization (`app/main.py`):**
        *   Initialize the Sentry SDK early, including relevant integrations.
            ```python
            # app/main.py
            import sentry_sdk
            from sentry_sdk.integrations.fastapi import FastAPIIntegration
            from sentry_sdk.integrations.starlette import StarletteIntegration
            from sentry_sdk.integrations.celery import CeleryIntegration
            from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
            from sentry_sdk.integrations.redis import RedisIntegration
            from sentry_sdk.integrations.httpx import HttpxIntegration
            # from sentry_sdk.integrations.elasticsearch import ElasticsearchIntegration # If using elasticsearch-py client directly
            from app.core.config import settings

            # app = FastAPI(...) # Defined earlier

            if settings.SENTRY_DSN:
                sentry_sdk.init(
                    dsn=str(settings.SENTRY_DSN), # Ensure DSN is a string from Pydantic HttpUrl
                    traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
                    profiles_sample_rate=settings.SENTRY_PROFILES_SAMPLE_RATE,
                    environment=settings.ENVIRONMENT,
                    release=settings.APP_VERSION,
                    send_default_pii=False, # Be cautious with PII
                    attach_stacktrace=True,
                    integrations=[
                        FastAPIIntegration(transaction_style="endpoint"), # or "url"
                        StarletteIntegration(),
                        CeleryIntegration(),
                        SqlalchemyIntegration(),
                        RedisIntegration(), # For redis-py
                        HttpxIntegration(), # For httpx client if used directly
                        # ElasticsearchIntegration(), # If applicable
                    ],
                )
            ```
    *   **8.3.2. Pydantic Settings (`app/core/config.py`):**
        *   Ensure these settings are defined:
            ```python
            # In Settings class:
            # from pydantic import HttpUrl
            # SENTRY_DSN: Optional[HttpUrl] = None
            # SENTRY_TRACES_SAMPLE_RATE: float = 0.1 # Default value
            # SENTRY_PROFILES_SAMPLE_RATE: float = 0.1 # Default value
            # APP_VERSION: str = "0.1.0" # Can be set via env var during build/deploy
            ```

    ### 8.4. Structured Logging Setup (`app/core/logging_config.py`, `app/core/request_context.py`, `app/core/middleware/request_id_middleware.py`, `app/main.py`)
    *   (As detailed in the previous response - includes `RequestIDMiddleware`, `CustomJsonFormatter`, and `setup_logging()` function to be called in `app/main.py` `on_startup` or before app initialization).

    ### 8.5. Health Check Endpoints (`app/features/health/router.py` and `app/main.py`)
    *   (As detailed in the previous response - includes `/live` and `/ready` endpoints, with the readiness probe checking DB, Redis, and other critical dependencies).
    *   Mount the health router in `app/main.py`:
        ```python
        # app/main.py
        # from app.features.health import router as health_router
        # app.include_router(health_router)
        ```

## 9. Integration & Usage Patterns

    This section provides examples of how monitoring components are used or impact development.

    ### 9.1. Accessing Prometheus Metrics
    *   The `/metrics` endpoint exposed by `starlette-prometheus` will be scraped by a Prometheus server.
    *   Dashboards in Grafana will query Prometheus for these metrics.

    ### 9.2. Using Custom Prometheus Metrics
    *   Import and use the defined custom metrics in your application code.
        ```python
        # app/features/orders/service.py
        # from app.core.metrics import ENTITIES_CREATED_COUNTER, SERVICE_FUNCTION_DURATION_SECONDS
        # import time

        # async def create_order_service(db: AsyncSession, order_in: ..., organization_id: int):
        #     with SERVICE_FUNCTION_DURATION_SECONDS.labels(
        #         service_name="order_service", function_name="create_order"
        #     ).time(): # Auto-observes duration
        #         # ... order creation logic ...
        #         # new_order = ...
        #         ENTITIES_CREATED_COUNTER.labels(
        #             entity_type="order",
        #             organization_id=str(organization_id)
        #         ).inc()
        #     return new_order
        ```

    ### 9.3. Viewing Errors in Sentry
    *   Unhandled exceptions in FastAPI, Starlette, Celery, SQLAlchemy, etc. (with configured integrations) will automatically be reported to Sentry.
    *   Access the Sentry UI to view error details, stack traces, context, and manage issues.

    ### 9.4. Manual Error Reporting and Context Enrichment for Sentry
    *   Use `sentry_sdk.capture_exception(e)` for handled exceptions you still want to report.
    *   Use `sentry_sdk.capture_message("Informational message")` for non-error events.
    *   Enrich Sentry events with user and tag information, typically in authentication middleware/dependencies or where context is available:
        ```python
        # Example in an authentication dependency (app/core/auth_dependencies.py)
        # import sentry_sdk
        # from app.users.schemas import UserRead # Your user Pydantic schema

        # async def get_current_active_user(...) -> UserRead:
        #     # ... (authentication logic to get 'user' object) ...
        #     if user:
        #         user_context = {"id": str(user.id), "username": user.username, "email": user.email}
        #         # if hasattr(user, 'organization_id') and user.organization_id:
        #         #     user_context["organization_id"] = str(user.organization_id)
        #         #     sentry_sdk.set_tag("organization_id", str(user.organization_id))
        #         sentry_sdk.set_user(user_context)
        #     return user
        ```

    ### 9.5. Correlating Logs, Traces, and Errors
    *   **Request ID:** The `request_id` (from `RequestIDMiddleware` and included in structured logs) is crucial.
        *   Include `request_id` as a custom tag in Sentry events: `sentry_sdk.set_tag("request_id", get_request_id())`.
        *   If using OpenTelemetry, ensure `request_id` is part of the trace context or added as a span attribute.
    *   This allows you to search for a `request_id` across Loki (logs), Sentry (errors), and your tracing system (Jaeger/Zipkin) to see the full picture of a problematic request.

    ### 9.6. Utilizing Health Checks
    *   Container orchestrators (Kubernetes, ECS) will use `/healthz/live` to determine if a container instance needs restarting.
    *   They will use `/healthz/ready` to determine if an instance should receive traffic. If the readiness probe fails, the instance is temporarily removed from the load balancer.
    *   External uptime monitoring services can ping these endpoints.
