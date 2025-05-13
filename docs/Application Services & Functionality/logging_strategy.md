# Logging Strategy (FastAPI Edition)

## 1. Overview

- **Purpose**: To define a consistent and effective strategy for application logging throughout the FastAPI-based ERP system. Effective logging is crucial for debugging, monitoring, auditing, and understanding application behavior in all environments.
- **Scope**: Covers log levels, log format (structured JSON), contextual information to include in logs, log output destinations, and integration with log management systems.
- **Goal**: To produce informative, structured, and easily parsable logs that provide valuable insights for developers, SREs, and support personnel, while being mindful of performance and PII (Personally Identifiable Information).

## 2. Core Principles

- **Structured Logging (JSON):** All application logs will be in JSON format to facilitate parsing, searching, and analysis by log management systems.
- **Contextual Information:** Logs must include relevant context (e.g., timestamp, level, logger name, request ID, user ID, organization ID, module, function, line number) to allow for effective correlation and troubleshooting.
- **Appropriate Log Levels:** Use standard log levels (DEBUG, INFO, WARNING, ERROR, CRITICAL) consistently and appropriately.
- **Performance Consideration:** Logging should be efficient. Avoid excessive logging of large objects or overly verbose messages in performance-sensitive code paths, especially in production.
- **Security & PII:** Sensitive information (passwords, API keys, raw PII not explicitly intended for logging) must **not** be logged. Implement mechanisms for filtering or masking if necessary.
- **Centralized Collection:** Logs from all application instances and components (FastAPI app, Celery workers) will be collected and aggregated into a central log management system.
- **Actionable Logs:** Logs should provide enough information to understand events, diagnose issues, or trigger alerts without excessive noise.

## 3. Logging Stack & Tools

- **Python Standard `logging` Module:** The primary interface for generating log messages within the application.
- **JSON Formatter:** **`python-json-logger`** library will be used to format log records into JSON.
  - Add to `requirements/base.txt`: `python-json-logger>=2.0.0,<2.1.0`.
- **Log Output:**
  - **Development:** Logs can output to `stdout`/`stderr` for easy viewing.
  - **Production/Staging (Containerized):** Logs **must** output to `stdout`/`stderr`. Container orchestration platforms (Docker, Kubernetes) will capture these streams.
- **Log Collection Agent:** **Promtail** (for Loki) or **Fluentd/Filebeat** (for ELK/EFK stack). These agents run alongside application containers or on hosts to collect logs from `stdout`/`stderr` (or files, if absolutely necessary) and forward them.
- **Log Aggregation & Querying System:** **Loki** (with Grafana for querying/visualization) or an **ELK/EFK stack** (Elasticsearch, Logstash/Fluentd, Kibana). (As defined in `monitoring_strategy.md`).

## 4. Log Format and Standard Fields

Each JSON log entry will contain a standard set of fields:

- `timestamp`: ISO 8601 formatted timestamp with timezone (UTC preferred). (e.g., `2023-10-27T14:35:22.123Z`)
- `level`: Log level string (e.g., "INFO", "ERROR", "DEBUG").
- `message`: The primary log message string.
- `logger_name`: Name of the logger that emitted the record (e.g., `app.features.users.service`).
- `module`: The Python module where the log originated (e.g., `service.py`).
- `funcName`: The name of the function/method where the log originated.
- `lineno`: The line number where the log originated.
- `request_id`: Unique ID for the HTTP request (if log is within a request context).
- `trace_id`, `span_id`: (Optional, from OpenTelemetry) For distributed tracing correlation.
- `user_id`: Authenticated user's ID (if available and relevant).
- `organization_id`: Current organization's ID (if available and relevant).
- `environment`: Application environment (e.g., "development", "staging", "production" from `settings.ENVIRONMENT`).
- `application_name`: Application name (e.g., from `settings.APP_NAME`).
- `version`: Application version (e.g., from `settings.APP_VERSION`).
- **Custom Fields:** Additional key-value pairs specific to the log event (e.g., `order_id`, `product_sku`, `error_details`).

## 5. Log Levels Usage Guidelines

- **`DEBUG`**: Detailed information, typically of interest only when diagnosing problems. Includes detailed diagnostic information, variable states, granular step-by-step execution. **Disabled in production by default.**
- **`INFO`**: Confirmation that things are working as expected. Routine operations, system startup/shutdown, significant lifecycle events (e.g., "User X logged in", "Order Y created", "Report Z generated").
- **`WARNING`**: An indication that something unexpected happened, or an indication of some problem in the near future (e.g., "disk space low"). The software is still working as expected, but the event should be noted. Examples: Deprecated API usage, recoverable errors, unusual but non-critical conditions.
- **`ERROR`**: Due to a more serious problem, the software has not been able to perform some function. Typically indicates an unhandled exception during request processing or task execution that prevented an operation from completing.
- **`CRITICAL`**: A serious error, indicating that the program itself may be unable to continue running. Very rare in web applications; usually reserved for catastrophic failures.

## 6. Contextual Logging

### 6.1. Request ID Injection

- A unique `request_id` will be generated for each incoming HTTP request (or read from an `X-Request-ID` header if provided by an upstream proxy/load balancer).
- This `request_id` will be made available throughout the request's lifecycle using a `contextvars.ContextVar`.
- A custom logging formatter (`CustomJsonFormatter`) will automatically include the `request_id` in all log messages emitted during that request.
- This allows tracing all log entries related to a single API call.

### 6.2. User and Organization Context

- After successful authentication and organization context resolution, `user_id` and `organization_id` should be added to the logging context for subsequent log messages within that request.
- This can be achieved by:
  - Passing them explicitly as `extra` data to logger calls: `logger.info("User action", extra={"user_id": uid, "org_id": oid})`.
  - Setting them in a `ContextVar` and having the `CustomJsonFormatter` include them.
  - Using a custom `LoggerAdapter` that injects this context.

### 6.3. Celery Task Context

- Celery tasks should log their `task_id`.
- If a task is initiated by an HTTP request, the `request_id` from the request should be passed to the Celery task and included in the task's logs for end-to-end tracing.
  - Celery signals (`before_task_publish`, `after_task_publish`) can be used to inject `request_id` into task headers if available in the publisher's context.
  - The task itself can then retrieve it from `self.request.correlation_id` or a custom header.

## 7. PII and Sensitive Data in Logs

- **Strict Prohibition:** Passwords, full API keys, session tokens, credit card numbers, and other highly sensitive PII **must never be logged.**
- **Data Masking/Filtering:**
  - Be cautious when logging entire request bodies or Pydantic models. Use Pydantic's `model_dump(exclude={'sensitive_field'})` or similar mechanisms if logging serialized objects.
  - If raw request/response logging is ever enabled for deep debugging (should be temporary and highly restricted), implement filters to mask sensitive fields.
- **Review:** Periodically review log contents in staging to ensure no accidental leakage of sensitive data.

## 8. Log Output and Collection

- **FastAPI Application & Uvicorn:** Configure to log to `stdout`/`stderr`. Uvicorn has its own access log format which can also be configured (or disabled if FastAPI middleware handles access logging more richly).
- **Celery Workers/Beat:** Configure Celery logging to also output structured JSON to `stdout`/`stderr`.
- **Containerization:** When running in Docker/Kubernetes, these `stdout`/`stderr` streams are captured by the container runtime.
- **Log Agent (Promtail/Fluentd/Filebeat):** Deployed on nodes or as sidecars to collect container logs and forward them to the central log aggregation system (Loki or ELK/EFK).

## 9. General Setup Implementation Details

    This section outlines the core setup for structured JSON logging.

    ### 9.1. Library Installation
    *   Ensure `python-json-logger>=2.0.0,<2.1.0` is in `requirements/base.txt`.

    ### 9.2. Request Context (`app/core/request_context.py`)
    *   Implement `request_id_ctx_var`, `get_request_id()`, `set_request_id()` using `contextvars` as shown in the `monitoring_strategy.md` (Section 8.4. Structured Logging Setup).
    *   Optionally, add similar `ContextVar` for `user_id` and `organization_id` if you want them to be automatically picked up by the formatter globally for a request, once set.

    ### 9.3. Request ID Middleware (`app/core/middleware/request_id_middleware.py`)
    *   Implement `RequestIDMiddleware` as shown in `monitoring_strategy.md` (Section 8.4). This middleware sets the `request_id_ctx_var` for each request.

    ### 9.4. Custom JSON Formatter (`app/core/logging_config.py`)
    *   Implement `CustomJsonFormatter(jsonlogger.JsonFormatter)` as shown in `monitoring_strategy.md` (Section 8.4). This formatter adds `timestamp`, `level`, `logger_name`, `module`, `funcName`, `lineno`, `request_id` (from context var), `environment`, `application_name`, `version` to each log record.

    ### 9.5. Logging Configuration Function (`app/core/logging_config.py`)
    *   Implement `setup_logging()` function as shown in `monitoring_strategy.md` (Section 8.4). This function:
        *   Sets the root logger level based on `settings.DEBUG_MODE`.
        *   Removes existing handlers (if any).
        *   Adds a `StreamHandler` (for `stdout`/`stderr`) using the `CustomJsonFormatter`.
        *   Configures log levels for noisy libraries like `uvicorn.access` or `sqlalchemy.engine`.

    ### 9.6. Initialize Logging in `app/main.py`
    *   Call `setup_logging()` very early in `app/main.py`, before the FastAPI app instance is created.
    *   Add `RequestIDMiddleware` to the FastAPI app's middleware stack.
        ```python
        # app/main.py
        # from app.core.logging_config import setup_logging
        # from app.core.middleware.request_id_middleware import RequestIDMiddleware
        # from app.core.middleware.context_logging_middleware import ContextLoggingMiddleware # If creating one for user/org

        # setup_logging() # Call early

        # app = FastAPI(...)
        # app.add_middleware(RequestIDMiddleware)
        # # Optional: app.add_middleware(ContextLoggingMiddleware) # To set user/org in ContextVars post-auth
        # # ... other middleware ...
        ```

## 10. Integration & Usage Patterns

    ### 10.1. Getting a Logger Instance
    *   In any Python module:
        ```python
        import logging
        logger = logging.getLogger(__name__) # Standard practice
        ```

    ### 10.2. Basic Logging
        ```python
        # logger.debug("Detailed diagnostic information for a specific variable.", extra={"variable_name": var_value})
        # logger.info("User successfully created.", extra={"new_user_id": user.id, "org_id": user.organization_id})
        # logger.warning("Payment gateway returned a retryable error.", extra={"gateway_response": resp_code, "order_id": order.id})
        # try:
        #     # ... some operation ...
        # except Exception as e:
        #     logger.error("Failed to process order.", exc_info=True, extra={"order_id": order.id, "error_details": str(e)})
        #     # exc_info=True automatically includes stack trace information
        ```
    *   The `extra` dictionary allows adding custom fields to the JSON log output. The `CustomJsonFormatter` can be adapted to automatically include certain common `extra` fields at the top level of the JSON if desired.

    ### 10.3. Logging in Celery Tasks
    *   Get a logger within the Celery task as usual.
    *   To correlate with the initiating HTTP request, pass the `request_id` to the task and log it.
        ```python
        # from app.core.celery_app import celery_app
        # from app.core.request_context import get_request_id # If task itself needs to set it for its context

        # @celery_app.task(bind=True)
        # def my_celery_task(self, data_id: int, originating_request_id: Optional[str] = None):
        #     logger = my_celery_task.get_logger() # Celery's task logger
        #     log_extra = {"data_id": data_id, "celery_task_id": self.request.id}
        #     if originating_request_id:
        #         log_extra["request_id"] = originating_request_id
        #         # Optionally, set it in contextvar if other functions in task use it
        #         # from app.core.request_context import set_request_id, request_id_ctx_var
        #         # token = request_id_ctx_var.set(set_request_id(originating_request_id))
        #         # try:
        #         #    ... task logic ...
        #         # finally:
        #         #    request_id_ctx_var.reset(token)


        #     logger.info("Processing data in Celery task.", extra=log_extra)
        #     # ... task logic ...
        ```

    ### 10.4. Reviewing Logs
    *   Access logs via the configured centralized log management system (Loki/Grafana or ELK/Kibana).
    *   Filter and search logs using fields like `request_id`, `user_id`, `organization_id`, `level`, `logger_name`.

How does this detailed logging strategy look?
