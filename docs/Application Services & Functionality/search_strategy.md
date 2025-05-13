
# Search Strategy (Elasticsearch with FastAPI)

## 1. Overview

*   **Purpose**: To define the strategy for implementing robust full-text search capabilities across relevant ERP entities (e.g., Products, Organizations, Stored Files, Orders) using Elasticsearch, integrated with the FastAPI application.
*   **Scope**: Covers Elasticsearch client selection, data indexing/synchronization from PostgreSQL to Elasticsearch, Elasticsearch index/mapping definitions, API design for search queries, and permission handling for search results.
*   **Chosen Technology**: **Elasticsearch** (Version 8.x+ or latest compatible), **`elasticsearch-py` (async client `elasticsearch.AsyncElasticsearch`)**.

## 2. Core Principles

*   **Decoupled Indexing**: Writes to Elasticsearch (indexing) will be asynchronous (via Celery tasks) to avoid impacting API request performance and to ensure resilience.
*   **Eventual Consistency**: A brief delay between data creation/updates in PostgreSQL and their availability in Elasticsearch search results is acceptable.
*   **Targeted & Relevant Indexing**: Only index fields necessary for searching and filtering. Use appropriate Elasticsearch analyzers and mappings for relevance.
*   **Secure Search**: Search results must strictly adhere to user permissions and organization/data scoping.
*   **Scalability**: Elasticsearch infrastructure should be scalable independently of the application.
*   **Maintainability**: Clear definitions for Elasticsearch mappings and a consistent indexing process.

## 3. Elasticsearch Client & Configuration (Strategic Overview)

*   **Client Library**: `elasticsearch-py` (async client `elasticsearch.AsyncElasticsearch`).
*   **Configuration (`app/core/config.py`):** `ELASTICSEARCH_HOSTS`, `ELASTICSEARCH_USERNAME`, `ELASTICSEARCH_PASSWORD`.
*   **Client Instantiation (`app/core/es_client.py`):** Singleton or dependency for `AsyncElasticsearch` client.

## 4. Index & Mapping Definitions (Strategic Overview)

*   Store Elasticsearch index mapping definitions (e.g., in `app/features/search/es_mappings/` or per feature).
*   Mappings define fields, types (text, keyword, date, nested), analyzers, and other settings.
*   Initial setup script/Alembic migration to create indexes and apply mappings.

## 5. Data Indexing (Synchronization - Strategic Overview)

*   **Primary Method: Asynchronous Celery Tasks.**
    *   Triggered by CUD operations on SQLAlchemy models (via service layer calls after DB commit).
    *   Tasks fetch data from PostgreSQL and index/update/delete documents in Elasticsearch.
*   **Alternative (for specific use cases or re-indexing):** Batch indexing scripts/Celery tasks.

## 6. Search API (Strategic Overview)

*   FastAPI endpoints (e.g., `GET /api/v1/search/`) accept search queries, filters, pagination, and sorting parameters.
*   Services use `AsyncElasticsearch` client to build and execute Elasticsearch queries.
*   Results are processed, permissions are applied, and data may be enriched by fetching full details from PostgreSQL if needed.

## 7. General Setup Implementation Details

    This section details the foundational setup for Elasticsearch integration.

    ### 7.1. Library Installation
    *   Ensure `elasticsearch>=8.0.0,<9.0.0` (or latest stable that supports your ES version) is in `requirements/base.txt`.

    ### 7.2. Pydantic Settings (`app/core/config.py`)
    *   Define Elasticsearch connection settings:
        ```python
        # In Settings class (app/core/config.py)
        # ...
        ELASTICSEARCH_HOSTS: List[str] = ["http://localhost:9200"] # Example for local
        ELASTICSEARCH_USERNAME: Optional[str] = None
        ELASTICSEARCH_PASSWORD: Optional[str] = None # From secrets manager via env
        ELASTICSEARCH_INDEX_PREFIX: str = "erp_dev" # To namespace indices per environment (e.g., "erp_prod")
        # ELASTICSEARCH_TIMEOUT_SECONDS: int = 10 # Default timeout for ES client
        # ELASTICSEARCH_MAX_RETRIES: int = 3
        # ELASTICSEARCH_RETRY_ON_TIMEOUT: bool = True
        ```

    ### 7.3. Elasticsearch Client Module (`app/core/es_client.py`)
    *   Provide a singleton `AsyncElasticsearch` client instance, accessible via a dependency.
        ```python
        # app/core/es_client.py
        from elasticsearch import AsyncElasticsearch, ConnectionError as ESConnectionError
        from app.core.config import settings
        from typing import Optional, List
        import logging

        logger = logging.getLogger(__name__)
        _es_client_instance: Optional[AsyncElasticsearch] = None

        async def init_es_client():
            """Initializes the Elasticsearch client."""
            global _es_client_instance
            if _es_client_instance is None:
                es_hosts_config: List[Dict[str, Any]] = []
                for host_url in settings.ELASTICSEARCH_HOSTS:
                    parsed_url = urlparse(host_url)
                    host_dict = {"host": parsed_url.hostname, "port": parsed_url.port or (443 if parsed_url.scheme == 'https' else 80)}
                    if parsed_url.scheme == 'https':
                        host_dict["use_ssl"] = True
                        host_dict["verify_certs"] = True # Adjust if using self-signed certs in dev
                    es_hosts_config.append(host_dict)
                
                http_auth_tuple: Optional[tuple[str, str]] = None
                if settings.ELASTICSEARCH_USERNAME and settings.ELASTICSEARCH_PASSWORD:
                    http_auth_tuple = (settings.ELASTICSEARCH_USERNAME, settings.ELASTICSEARCH_PASSWORD)

                try:
                    logger.info(f"Initializing Elasticsearch client for hosts: {settings.ELASTICSEARCH_HOSTS}")
                    _es_client_instance = AsyncElasticsearch(
                        hosts=settings.ELASTICSEARCH_HOSTS, # Can also pass the list of dicts directly
                        http_auth=http_auth_tuple,
                        # timeout=settings.ELASTICSEARCH_TIMEOUT_SECONDS,
                        # max_retries=settings.ELASTICSEARCH_MAX_RETRIES,
                        # retry_on_timeout=settings.ELASTICSEARCH_RETRY_ON_TIMEOUT,
                        # sniffer_timeout=60, # If using sniffing
                        # sniff_on_start=True, sniff_on_connection_fail=True,
                    )
                    if not await _es_client_instance.ping():
                        raise ESConnectionError("Elasticsearch ping failed on init.")
                    logger.info("Successfully connected to Elasticsearch.")
                except Exception as e:
                    logger.error(f"Failed to initialize Elasticsearch client: {e}", exc_info=True)
                    _es_client_instance = None # Ensure it's None if init fails
            return _es_client_instance

        async def get_es_client() -> Optional[AsyncElasticsearch]:
            """FastAPI dependency to get an Elasticsearch client instance."""
            if _es_client_instance is None:
                await init_es_client()
            if _es_client_instance is None: # Check again after await
                 logger.error("Elasticsearch client is not available.")
                 # Depending on how critical ES is, you might raise HTTPException(503)
                 # or allow parts of the app to function without search.
            return _es_client_instance

        async def close_es_client():
            """Closes the Elasticsearch client."""
            global _es_client_instance
            if _es_client_instance:
                await _es_client_instance.close()
                _es_client_instance = None
                logger.info("Elasticsearch client closed.")

        # In app/main.py:
        # @app.on_event("startup")
        # async def on_startup():
        #     await init_es_client()
        #     # ...
        #
        # @app.on_event("shutdown")
        # async def on_shutdown():
        #     await close_es_client()
        #     # ...
        ```
        *Note: Added `urlparse` for more robust host parsing for the `AsyncElasticsearch` client if full URLs are in `ELASTICSEARCH_HOSTS`.*

    ### 7.4. Index and Mapping Management (`app/features/search/es_management.py`)
    *   Define Python dictionaries or use `elasticsearch-dsl` `Document` classes for your ES index mappings.
    *   Create a utility script or Celery task to initialize indexes and apply mappings.
        ```python
        # app/features/search/es_mappings/product_mapping.py (Example)
        # PRODUCT_INDEX_NAME_TEMPLATE = f"{settings.ELASTICSEARCH_INDEX_PREFIX}_products" # e.g., erp_dev_products

        # product_index_mapping = {
        #     "mappings": {
        #         "properties": {
        #             "id": {"type": "integer"},
        #             "sku": {"type": "keyword"},
        #             "name": {"type": "text", "analyzer": "standard", "fields": {"keyword": {"type": "keyword"}}},
        #             "description": {"type": "text", "analyzer": "standard"},
        #             "price": {"type": "float"},
        #             "is_active": {"type": "boolean"},
        #             "organization_id": {"type": "integer"}, # For filtering search results
        #             "created_at": {"type": "date"},
        #             "updated_at": {"type": "date"},
        #             "tags": {"type": "keyword"},
        #             # Add localized fields if searching on them:
        #             # "name_fr": {"type": "text", "analyzer": "french"},
        #             # "description_fr": {"type": "text", "analyzer": "french"},
        #         }
        #     },
        #    "settings": { "number_of_shards": 1, "number_of_replicas": 0 } # Adjust for prod
        # }
        ```
        ```python
        # app/features/search/es_management.py (Conceptual)
        # from elasticsearch import AsyncElasticsearch, NotFoundError as ESNotFoundError
        # from .es_mappings.product_mapping import product_index_mapping, PRODUCT_INDEX_NAME_TEMPLATE
        # from app.core.config import settings

        # async def create_product_index(es_client: AsyncElasticsearch):
        #     index_name = PRODUCT_INDEX_NAME_TEMPLATE
        #     try:
        #         if not await es_client.indices.exists(index=index_name):
        #             await es_client.indices.create(index=index_name, body=product_index_mapping)
        #             logger.info(f"Created Elasticsearch index: {index_name}")
        #         else:
        #             logger.info(f"Elasticsearch index '{index_name}' already exists.")
        #             # Optionally, update mappings if changed (can be complex, might require reindex)
        #             # await es_client.indices.put_mapping(index=index_name, body=product_index_mapping["mappings"])
        #     except Exception as e:
        #         logger.error(f"Error creating/managing product index '{index_name}': {e}", exc_info=True)

        # async def setup_all_indices(es_client: AsyncElasticsearch):
        #    await create_product_index(es_client)
        #    # ... call create for other indices ...

        # This setup_all_indices can be called from an Alembic data migration,
        # a startup script, or a dedicated CLI command for the application.
        ```
    *   **Alembic for Index Creation:** Use an `op.execute_python()` in an Alembic migration to call `setup_all_indices()` when the application is first set up or when mappings change significantly.

    ### 7.5. Celery Tasks for Indexing (`app/features/search/tasks.py`)
    *   Define Celery tasks for indexing, updating, and deleting documents in Elasticsearch.
        ```python
        # app/features/search/tasks.py
        # from app.core.celery_app import celery_app
        # from app.core.db import AsyncSessionFactory
        # from app.core.es_client import get_es_client # This needs to work in Celery context
        # from .es_mappings.product_mapping import PRODUCT_INDEX_NAME_TEMPLATE
        # # from app.features.products.models import Product # Import the SQLAlchemy model
        # import logging

        # logger = logging.getLogger(__name__)

        # async def _get_es_client_for_task(): # Helper for Celery task ES client
        #    # Celery tasks run in separate processes, so global _es_client_instance from app.core.es_client
        #    # might not be initialized or might be the wrong one if that module is re-imported.
        #    # It's safer for tasks to create their own client instance or use a task-specific context.
        #    # This is a simplification; robust client management in tasks is important.
        #    from app.core.es_client import init_es_client as init_main_es_client, _es_client_instance as main_es_client
        #    if main_es_client is None: # Attempt to init if not already by main app context (less likely in worker)
        #        return await init_main_es_client()
        #    return main_es_client


        # @celery_app.task(name="search.index_product_document", max_retries=3, default_retry_delay=60)
        # async def index_product_document_task(product_id: int):
        #     es_client = await _get_es_client_for_task()
        #     if not es_client:
        #         logger.error(f"ES client not available for indexing product {product_id}. Retrying...")
        #         raise index_product_document_task.retry(countdown=60)

        #     async with AsyncSessionFactory() as db:
        #         # product = await db.get(Product, product_id) # Get fresh data
        #         # if not product:
        #         #     logger.warning(f"Product {product_id} not found for ES indexing. Skipping.")
        #         #     return

        #         # document_body = {
        #         #     "id": product.id, "sku": product.sku, "name": product.name,
        #         #     "description": product.description, "price": product.price,
        #         #     "is_active": product.is_active, "organization_id": product.organization_id,
        #         #     "created_at": product.created_at.isoformat(), "updated_at": product.updated_at.isoformat(),
        #         #     # Add tags, localized fields, etc.
        #         # }
        #         # For this example, creating dummy data
        #         document_body = {"id": product_id, "name": f"Product {product_id} Name"}


        #         index_name = PRODUCT_INDEX_NAME_TEMPLATE
        #         try:
        #             await es_client.index(index=index_name, id=str(product_id), document=document_body)
        #             logger.info(f"Successfully indexed product {product_id} in ES index {index_name}")
        #         except Exception as e:
        #             logger.error(f"Failed to index product {product_id} in ES: {e}", exc_info=True)
        #             raise index_product_document_task.retry(exc=e)


        # @celery_app.task(name="search.delete_product_document", max_retries=3, default_retry_delay=60)
        # async def delete_product_document_task(product_id: int):
        #     es_client = await _get_es_client_for_task()
        #     if not es_client: # Handle client not available
        #         logger.error(f"ES client not available for deleting product {product_id}. Retrying...")
        #         raise delete_product_document_task.retry(countdown=60)

        #     index_name = PRODUCT_INDEX_NAME_TEMPLATE
        #     try:
        #         await es_client.delete(index=index_name, id=str(product_id), ignore=[404]) # Ignore if already deleted
        #         logger.info(f"Successfully deleted product {product_id} from ES index {index_name}")
        #     except Exception as e:
        #         logger.error(f"Failed to delete product {product_id} from ES: {e}", exc_info=True)
        #         raise delete_product_document_task.retry(exc=e)
        ```
        *The `_get_es_client_for_task` helper is important because Celery tasks run in different processes and might not share the same initialized client as the FastAPI app.*

    ### 7.6. Docker Compose Service (Local Development)
    *   Include an Elasticsearch service in `docker-compose.yml`.
        ```yaml
        # docker-compose.yml
        # services:
        #   es01:
        #     image: docker.elastic.co/elasticsearch/elasticsearch:8.11.0 # Use a specific recent version
        #     container_name: es01
        #     environment:
        #       - discovery.type=single-node
        #       - xpack.security.enabled=false # For ease of local dev; set true with creds for more security
        #       - "ES_JAVA_OPTS=-Xms512m -Xmx512m" # Adjust memory as needed
        #     ulimits:
        #       memlock:
        #         soft: -1
        #         hard: -1
        #     volumes:
        #       - es_data01:/usr/share/elasticsearch/data
        #     ports:
        #       - "9200:9200"
        # volumes:
        #   es_data01:
        ```

## 8. Integration & Usage Patterns

    ### 8.1. Triggering Indexing Tasks from Service Layer
    *   After a successful database CUD operation in a service function, dispatch a Celery task.
        ```python
        # app/features/products/services/product_service.py
        # from app.features.search.tasks import index_product_document_task, delete_product_document_task

        # async def create_product(db: AsyncSession, product_in: schemas.ProductCreate, ...) -> models.Product:
        #     # ... (create product_db in PostgreSQL) ...
        #     # await db.flush()
        #     # await db.refresh(product_db)
        #     # index_product_document_task.delay(product_db.id) # Dispatch Celery task
        #     return product_db

        # async def update_product(db: AsyncSession, product_db: models.Product, ...) -> models.Product:
        #     # ... (update product_db in PostgreSQL) ...
        #     # index_product_document_task.delay(product_db.id)
        #     return product_db

        # async def delete_product(db: AsyncSession, product_id: int) -> Optional[models.Product]:
        #     # ... (delete product from PostgreSQL) ...
        #     # if deleted_product:
        #     #    delete_product_document_task.delay(product_id)
        #     return deleted_product
        ```

    ### 8.2. Search API Endpoint (`app/features/search/router.py`)
    *   Define path operations for search queries.
        ```python
        # app/features/search/router.py
        # from fastapi import APIRouter, Depends, Query, HTTPException
        # from elasticsearch import AsyncElasticsearch, exceptions as es_exceptions
        # from app.core.es_client import get_es_client
        # from app.core.auth_dependencies import get_current_active_user # For permissioned search
        # from app.users.schemas import UserRead
        # from typing import List, Dict, Any
        # from . import schemas as search_schemas # Pydantic models for search requests/responses

        # router = APIRouter(prefix="/search", tags=["Search"])

        # @router.get("/", response_model=search_schemas.SearchResults) # Define SearchResults Pydantic model
        # async def perform_search(
        #     query: str = Query(..., min_length=1, description="Search query string"),
        #     index_names: Optional[List[str]] = Query(None, description="Specific indices to search, e.g., ['erp_dev_products']"),
        #     # organization_id: Optional[int] = Query(None), # For org-scoped search
        #     # current_user: UserRead = Depends(get_current_active_user), # To apply permissions
        #     es: AsyncElasticsearch = Depends(get_es_client),
        #     # Add pagination params (from_ / size for ES)
        #     # Add filter params
        # ):
        #     if not es:
        #         raise HTTPException(status_code=503, detail="Search service unavailable")

        #     # Construct Elasticsearch query body (DSL)
        #     # This is where elasticsearch-dsl can be helpful for complex queries
        #     es_query_body = {
        #         "query": {
        #             "multi_match": {
        #                 "query": query,
        #                 "fields": ["name^3", "description", "sku", "tags"] # Example fields and boosting
        #             }
        #         },
        #         # "filter": [ # Add permission filters based on current_user.organization_id etc.
        #         #    {"term": {"organization_id": current_user.organization_id}}
        #         # ],
        #         # "from": from_offset, "size": page_size
        #     }

        #     target_indices = index_names or [f"{settings.ELASTICSEARCH_INDEX_PREFIX}_*"] # Search all app indices by default

        #     try:
        #         search_response = await es.search(
        #             index=",".join(target_indices), # Comma-separated string of indices
        #             body=es_query_body,
        #             # from_=from_offset, size=page_size
        #         )
        #     except es_exceptions.ElasticsearchException as e:
        #         logger.error(f"Elasticsearch query failed: {e}", exc_info=True)
        #         raise HTTPException(status_code=500, detail="Search query failed")

        #     hits = [hit['_source'] for hit in search_response['hits']['hits']]
        #     total_hits = search_response['hits']['total']['value']
        #     # Process hits (e.g., enrich with more data from DB if needed, though often not for search lists)
        #     # Ensure results are permission-checked if not filtered in ES query
        #     return search_schemas.SearchResults(items=hits, total=total_hits)
        ```

    ### 8.3. Handling Permissions in Search
    *   **Filter at Query Time (Preferred):** Add filters to the Elasticsearch query based on the authenticated user's `organization_id`, roles, or other access control attributes. This requires indexing these attributes (e.g., `organization_id`) in your Elasticsearch documents.
    *   **Post-Query Filtering (Less Ideal):** Fetch a broader set of results from Elasticsearch and then filter them in the application layer based on permissions. This can be inefficient and lead to inaccurate pagination/counts.
