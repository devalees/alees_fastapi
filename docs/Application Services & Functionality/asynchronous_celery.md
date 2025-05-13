# Asynchronous Task Processing Strategy (Celery with FastAPI)

## 1. Overview

    * Purpose: To establish the setup for using Celery with the FastAPI application for asynchronous task execution and scheduling, leveraging a custom database-backed scheduler for Celery Beat.
    * Scope: Celery application instance definition, configuration, integration with FastAPI, task definition conventions, and the strategy for Celery Beat using a custom database scheduler.
    * Chosen Technology: **Celery** (Target Version: 5.3.x), **Redis** as the Message Broker and Result Backend. PostgreSQL (via SQLAlchemy) for storing Celery Beat schedule definitions.

## 2. Core Requirements

    * Enable Asynchronous Execution for long-running, CPU-bound, or critical operations.
    * FastAPI Integration for easy task dispatching.
    * Database Access for Tasks (SQLAlchemy `AsyncSession`).
    * Scalability of Celery workers.
    * Reliable & Dynamic Scheduling via Celery Beat with a custom database scheduler.

## 3. Celery Application Setup (Strategic Overview - `app/core/celery_config.py`)

    * Celery app instance (`celery_app`) definition.
    * Configuration from Pydantic `settings` (broker, backend, timezone, serializers).
    * Task auto-discovery (listing task modules in `include`).
    * Considerations for `async def` tasks within Celery.

## 4. Celery Beat with Custom Database Scheduler (Strategic Overview)

    * Rationale: Dynamic management of periodic tasks without Django Admin.
    * DB Models for Schedules (`app/tasks/scheduler_models.py`): `CrontabScheduleDB`, `IntervalScheduleDB`, `PeriodicTaskDB` using SQLAlchemy.
    * Custom Scheduler Class (`app/tasks/db_scheduler.py`): Inherits `celery.beat.Scheduler`, reads schedules from DB.
    * Configuration: `celery_app.conf.beat_scheduler` points to the custom scheduler.
    * Management: API endpoints (future PRD) for CRUD on schedule DB models.

## 5. Integration with FastAPI (Strategic Overview)

    * Dispatching tasks (`.delay()`, `.apply_async()`).
    * Retrieving task results (`AsyncResult`).

## 6. Local Development & Running Workers/Beat (Strategic Overview)

    * Separate `celery worker` and `celery beat` processes.
    * Docker Compose service definitions.

## 7. Monitoring & Testing (Strategic Overview)

    * Monitoring with Flower or Prometheus (`celery-exporter`).
    * Testing with `task_always_eager=True`.

## 8. General Setup Implementation Details

    This section details the foundational setup for Celery and its custom Beat scheduler.

    ### 8.1. Library Installation
    *   Ensure `celery>=5.3.0,<5.4.0` is in `requirements/base.txt`.
    *   Ensure `redis[hiredis]>=5.0.0,<5.1.0` (for broker/backend) is in `requirements/base.txt`.
    *   (SQLAlchemy, asyncpg are already dependencies for the main DB).

    ### 8.2. Pydantic Settings (`app/core/config.py`)
    *   Define Celery-related settings:
        ```python
        # In Settings class (app/core/config.py)
        # ...
        # REDIS_HOST, REDIS_PORT, REDIS_PASSWORD are already defined
        # REDIS_CELERY_BROKER_DB: int = 0
        # REDIS_CELERY_RESULT_DB: int = 0 # Can be same as broker DB

        # @property
        # def CELERY_BROKER_URL(self) -> str:
        #     auth = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
        #     return f"redis://{auth}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_CELERY_BROKER_DB}"

        # @property
        # def CELERY_RESULT_BACKEND(self) -> str:
        #     auth = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
        #     return f"redis://{auth}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_CELERY_RESULT_DB}"

        CELERY_FLOWER_PORT: int = 5555 # For local Flower monitoring

        # For custom DB scheduler (if it needs specific settings beyond main DB URL)
        # CELERY_BEAT_DB_SCHEDULER_SYNC_EVERY_SECONDS: int = 60 # How often Beat re-reads all schedules
        # CELERY_BEAT_DB_SCHEDULER_MAX_INTERVAL_SECONDS: int = 300 # Max seconds Beat sleeps
        ```
        *The actual `CELERY_BROKER_URL` and `CELERY_RESULT_BACKEND` should be full URLs constructed in `settings` or provided directly if simpler.*

    ### 8.3. Celery Application Initialization (`app/core/celery_app.py`)
        *   Create the Celery application instance. (Slight change from `celery_config.py` to `celery_app.py` for clarity, or keep in `celery_config.py`).
        ```python
        # app/core/celery_app.py
        from celery import Celery
        from app.core.config import settings

        # Define the list of modules Celery should inspect for tasks
        # This should ideally be discoverable or configurable if many features add tasks
        TASK_MODULES = [
            'app.features.reports.tasks', # Example
            'app.features.data_processing.tasks', # Example
            # Add other task modules here
            'app.tasks.periodic_health_checks', # Example for a general periodic task
        ]

        celery_app = Celery(
            "erp_worker", # A name for your Celery app
            broker=settings.CELERY_BROKER_URL,
            backend=settings.CELERY_RESULT_BACKEND,
            include=TASK_MODULES
        )

        celery_app.conf.update(
            task_serializer='json',
            accept_content=['json'],
            result_serializer='json',
            timezone=settings.TIME_ZONE, # From Pydantic settings
            enable_utc=True,
            worker_send_task_events=True, # Useful for Flower/monitoring
            task_send_sent_event=True,
            # Beat Scheduler Configuration
            beat_scheduler='app.tasks.db_scheduler.DatabaseScheduler', # Path to your custom scheduler
            # Optional: Celery Beat specific settings for the custom scheduler, if needed
            # beat_db_sync_every=settings.CELERY_BEAT_DB_SCHEDULER_SYNC_EVERY_SECONDS,
            # beat_max_interval=settings.CELERY_BEAT_DB_SCHEDULER_MAX_INTERVAL_SECONDS,

            # Task execution settings (examples, tune as needed)
            # task_acks_late = True # For more robust task handling
            # worker_prefetch_multiplier = 1 # Can help with long-running tasks
            # worker_concurrency = 4 # Default is num CPUs, adjust based on task I/O vs CPU nature
        )

        # Optional: If you have tasks that are `async def` and you want Celery to handle
        # the asyncio event loop. Celery 5 has better native support.
        # Ensure your worker startup command uses an appropriate pool (e.g., eventlet, gevent if needed,
        # or if Celery's default pool handles asyncio well for your tasks).
        # If calling async code from within a synchronous Celery task, use asgiref.sync:
        # from asgiref.sync import async_to_sync
        # result = async_to_sync(my_async_function)(param1, param2)

        # Example: Load task Pydantic models if they are defined separately (less common for Celery)
        # celery_app.autodiscover_tasks(lambda: settings.INSTALLED_APPS_WITH_TASKS, related_name='tasks')
        ```

    ### 8.4. SQLAlchemy Models for Beat Schedules (`app/tasks/scheduler_models.py`)
    *   Define `CrontabScheduleDB`, `IntervalScheduleDB`, `PeriodicTaskDB` SQLAlchemy models.
        *   (Full model definitions were provided in the previous Celery discussion, including `get_schedule`, `get_args`, `get_kwargs` helpers on `PeriodicTaskDB`).
    *   These tables need to be created by an Alembic migration.

    ### 8.5. Custom Database Beat Scheduler (`app/tasks/db_scheduler.py`)
    *   Implement the `DatabaseScheduler(celery.beat.Scheduler)` class.
    *   **Key Methods to Override:**
        *   `__init__(self, *args, **kwargs)`: Initialize, get DB URL from Celery app config (passed from Pydantic settings). Create a synchronous SQLAlchemy engine/session factory for Beat's use (Beat itself is typically synchronous).
        *   `setup_schedule()`: Called once at Beat startup.
        *   `sync()`: Called periodically by Beat. This method should:
            1.  Query the `PeriodicTaskDB` table for all enabled schedules.
            2.  Convert these DB records into `celery.beat.ScheduleEntry` objects.
            3.  Update `self.schedule` (a dict in the base Scheduler class) with these entries.
            4.  Handle updates to `last_run_at`, `total_run_count` in the `PeriodicTaskDB` after tasks are sent.
        *   `max_interval`: Return the configured `beat_max_interval`.
        *   `close()`: Clean up database connections.
    *   This is a complex piece. The AI agent will need clear guidance or reference examples for a SQLAlchemy-based Celery Beat scheduler. It involves translating DB schedule rows into Celery's internal schedule format.

    ### 8.6. Alembic Migration for Scheduler Tables
    *   After defining `scheduler_models.py`, run `alembic revision --autogenerate -m "create_celery_beat_schedule_tables"` and `alembic upgrade head` to create these tables in your PostgreSQL database.

    ### 8.7. Docker Compose Services (`docker-compose.yml`)
    *   Define services for Celery worker(s) and Celery Beat.
        ```yaml
        # docker-compose.yml
        # services:
        #   # ... api, postgres, redis ...
        #   celery_worker:
        #     build: . # Same Docker image as the API
        #     command: celery -A app.core.celery_app.celery_app worker -l INFO -P eventlet # Or chosen pool
        #     volumes:
        #       - .:/app
        #     env_file:
        #       - .env
        #     depends_on:
        #       - redis
        #       - postgres # If tasks need DB immediately on start
        #     # environment: # Can override .env vars here
        #     #   C_FORCE_ROOT: "true" # If running as root in dev container, not for prod

        #   celery_beat:
        #     build: .
        #     command: celery -A app.core.celery_app.celery_app beat -l INFO --scheduler app.tasks.db_scheduler.DatabaseScheduler
        #     volumes:
        #       - .:/app
        #     env_file:
        #       - .env
        #     depends_on:
        #       - redis
        #       - postgres # Scheduler needs DB to read schedules
        ```

## 9. Integration & Usage Patterns

    This section provides examples of defining and using Celery tasks.

    ### 9.1. Defining Celery Tasks (`app/features/<feature_name>/tasks.py`)
    *   Tasks are Python functions decorated with `@celery_app.task`.
        ```python
        # app/features/reports/tasks.py
        from app.core.celery_app import celery_app
        from app.core.db import AsyncSessionFactory # Use the app's session factory
        # from .services import report_service # Example service
        import asyncio
        import logging

        logger = logging.getLogger(__name__)

        @celery_app.task(bind=True, name="reports.generate_sales_report", max_retries=3, default_retry_delay=60)
        async def generate_sales_report_task(self, report_params: dict, organization_id: int):
            logger.info(f"Starting sales report generation for org {organization_id}, params: {report_params}. Task ID: {self.request.id}")
            async with AsyncSessionFactory() as db_session: # Create a new session for the task
                try:
                    # report_url = await report_service.generate_and_store_report(
                    #     db_session,
                    #     params=report_params,
                    #     organization_id=organization_id
                    # )
                    # Simulating work
                    await asyncio.sleep(30)
                    report_url = f"/media/reports/sales_report_{organization_id}_{self.request.id}.pdf"
                    logger.info(f"Sales report generated for org {organization_id}. URL: {report_url}")
                    # await db_session.commit() # If service made changes
                    return {"report_url": report_url, "status": "success"}
                except Exception as e:
                    logger.error(f"Failed to generate sales report for org {organization_id}: {e}", exc_info=True)
                    # await db_session.rollback()
                    # self.update_state(state='FAILURE', meta={'exc_type': type(e).__name__, 'exc_message': str(e)})
                    raise self.retry(exc=e, countdown=60 * 5) # Retry after 5 minutes
        ```
    *   **Database Sessions in Tasks:** Tasks that interact with the database **must create their own `AsyncSession`** using `AsyncSessionFactory()`. They should not attempt to reuse sessions from FastAPI request contexts. Manage the session lifecycle (commit/rollback/close) within the task.
    *   **Async Tasks:** If tasks are `async def`, ensure your Celery worker pool (e.g., `-P eventlet` or `-P gevent` with appropriate monkeypatching, or Celery 5's improved solo pool for asyncio) can execute them correctly. If a synchronous task needs to call async code, use `asgiref.sync.async_to_sync`.

    ### 9.2. Dispatching Tasks from FastAPI Endpoints or Services
        ```python
        # app/features/reports/router.py
        # from fastapi import APIRouter, Depends, status, BackgroundTasks
        # from .tasks import generate_sales_report_task
        # from app.core.auth_dependencies import get_current_active_user
        # from app.users.schemas import UserRead

        # router = APIRouter(tags=["Reports"])

        # @router.post("/{organization_id}/sales-report/generate", status_code=status.HTTP_202_ACCEPTED)
        # async def trigger_sales_report_generation(
        #     organization_id: int,
        #     report_params_payload: dict, # Pydantic schema for params
        #     current_user: UserRead = Depends(get_current_active_user) # For auth & org context
        # ):
        #     # Authorization check: ensure current_user can access organization_id and generate reports
        #
        #     task = generate_sales_report_task.delay(
        #         report_params=report_params_payload,
        #         organization_id=organization_id
        #     )
        #     return {"task_id": task.id, "message": "Sales report generation has been queued."}
        ```

    ### 9.3. Managing Periodic Tasks (via API for Custom DB Scheduler)
    *   A separate set of API endpoints (e.g., `/api/v1/admin/periodic-tasks/`) will be created (based on the future "DB Operations App" PRD or a similar admin module) to CRUD records in `PeriodicTaskDB`, `CrontabScheduleDB`, `IntervalScheduleDB`.
    *   This allows administrators to dynamically define, enable, disable, and modify scheduled tasks without code changes or restarting Celery Beat (as Beat's `sync()` method will pick up changes from the DB).

    ### 9.4. Retrieving Task Status and Results
        ```python
        # from celery.result import AsyncResult
        # from app.core.celery_app import celery_app

        # @router.get("/tasks/{task_id}/status")
        # async def get_task_status(task_id: str):
        #     task_result = AsyncResult(task_id, app=celery_app)
        #     response = {
        #         "task_id": task_id,
        #         "status": task_result.status,
        #         "result": task_result.result if task_result.ready() else None,
        #     }
        #     if task_result.failed():
        #         response["error"] = str(task_result.info) # Or task_result.traceback
        #     return response
        ```

    ### 9.5. Using Celery Flower for Monitoring (Local/Dev)
    *   Run Flower: `celery -A app.core.celery_app.celery_app flower --port=5555`
    *   Access `http://localhost:5555` to monitor tasks and workers. This can be added as a service in `docker-compose.yml`.


