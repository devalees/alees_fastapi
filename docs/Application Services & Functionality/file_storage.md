Okay, great! Let's now provide the full, updated `file_storage_strategy.md` for FastAPI, including the "General Setup Implementation Details" and "Integration & Usage Patterns" sections, based on our decision to support both local and cloud (S3) backends with an abstraction layer.

---

**`file_storage_strategy.md` (FastAPI Edition - Full Version)**

# File Storage Strategy (FastAPI Edition)

## 1. Overview

*   **Purpose**: To define the strategy for storing, retrieving, and managing user-uploaded files and system-generated files within the FastAPI-based ERP application.
*   **Scope**: Covers the choice of storage backends (local filesystem and cloud), interaction patterns (upload/download mechanisms), metadata management, integration with search capabilities, and the necessary application setup and usage patterns.
*   **Goal**: Provide a reliable, secure, scalable, and configurable file storage solution that supports efficient file operations and searchability.

## 2. Core Principles

*   **Configurable Backends**: The system must support switching between local filesystem storage and cloud-based object storage (AWS S3 as primary cloud example) via application configuration.
*   **Abstraction Layer**: Application code will interact with a common storage service interface, abstracting the specifics of the chosen backend.
*   **Secure Access**: File uploads and downloads will be permission-controlled. Pre-signed URLs will be used for direct client interaction with cloud storage.
*   **Metadata Management**: Essential metadata for each stored file will be stored persistently in the primary PostgreSQL database.
*   **Searchability**: File metadata (and potentially extracted content) will be indexed in Elasticsearch.
*   **Asynchronous Operations**: File operations should be asynchronous where possible, especially interactions with cloud storage or large file processing.

## 3. Chosen Storage Backends & Technologies

*   **Primary Application Database (PostgreSQL via SQLAlchemy):** For storing file metadata (via a `StoredFile` model).
*   **Local Filesystem Storage:** For development, testing, or specific simple deployments.
*   **Cloud Object Storage (Primary for Production/Staging):** AWS S3 (Amazon Simple Storage Service).
*   **Client Libraries:**
    *   `aioboto3` (for asynchronous S3 operations).
    *   `aiofiles` (for asynchronous local file I/O).
    *   `python-multipart` (for FastAPI `UploadFile` handling).
*   **File Search Indexing:** Elasticsearch (details in `search_strategy.md`).

## 4. Configuration (`app/core/config.py` - Pydantic Settings)

*   **Key Settings:**
    ```python
    # In Pydantic Settings class (app/core/config.py)
    FILE_STORAGE_BACKEND: str = "local"  # Options: "local", "s3"
    LOCAL_MEDIA_ROOT: str = "/app/media" # Absolute path inside container for local storage
    LOCAL_MEDIA_URL_PREFIX: str = "/media" # URL prefix for serving local files

    # S3 Specific (if FILE_STORAGE_BACKEND is "s3")
    AWS_ACCESS_KEY_ID: Optional[str] = None     # From secrets manager
    AWS_SECRET_ACCESS_KEY: Optional[str] = None # From secrets manager
    AWS_S3_BUCKET_NAME: Optional[str] = None    # e.g., "my-erp-prod-filestorage"
    AWS_S3_REGION_NAME: Optional[str] = None    # e.g., "us-east-1"
    AWS_S3_ENDPOINT_URL: Optional[str] = None   # For MinIO/local S3: "http://minio:9000"
    AWS_S3_ADDRESSING_STYLE: str = "auto"       # e.g., "virtual" or "path"
    AWS_S3_SIGNATURE_VERSION: str = "s3v4"
    AWS_S3_FILE_OVERWRITE: bool = False
    AWS_S3_PRESIGNED_URL_EXPIRY_SECONDS: int = 3600
    ```

## 5. Storage Service Abstraction (Strategic Overview)

*   An abstraction layer (`app/core/storage_service.py`) will define a `BaseStorage` protocol/ABC with methods like `save`, `delete`, `get_download_url`, `get_upload_url`.
*   Concrete implementations: `LocalFileStorage` and `S3FileStorage`.
*   A factory function `get_storage_service()` will return an instance of the configured backend.

## 6. File Upload Workflow (Strategic Overview)

*   **Cloud (S3):** Client requests pre-signed upload URL -> Client uploads to S3 -> Client confirms upload to backend -> Backend saves metadata & triggers async indexing.
*   **Local:** Client uploads to FastAPI endpoint -> Backend saves file locally -> Backend saves metadata & triggers async indexing.

## 7. File Download/Access Workflow (Strategic Overview)

*   Client requests file -> Backend checks perms & gets metadata -> Backend generates download URL (pre-signed for S3, direct for local) using storage service -> Client downloads.

## 8. File Metadata Management (`StoredFile` Model - Strategic Overview)

*   A SQLAlchemy model (`StoredFile`) will store `file_key`, `original_filename`, `content_type`, `size`, `storage_backend`, `bucket_name`, `uploader_info`, `timestamps`, relationships.

## 9. Search Integration (Elasticsearch - Strategic Overview)

*   `StoredFile` metadata (and optionally extracted text content) indexed in Elasticsearch via async tasks.

## 10. General Setup Implementation Details

    This section details the one-time setup and core configurations for the file storage system.

    ### 10.1. Library Installation
    *   Ensure the following are present in `requirements/base.txt`:
        ```txt
        aioboto3>=10.0.0,<12.0.0  # Or latest stable compatible with botocore
        aiofiles>=23.1.0,<24.0.0  # Or latest stable
        python-multipart>=0.0.5,<0.1.0 # For FastAPI UploadFile
        # botocore is a dependency of aioboto3/boto3
        ```

    ### 10.2. Pydantic Settings (`app/core/config.py`)
    *   Verify all settings listed in Section 4 (Configuration) of this document are defined in your `Settings` class.

    ### 10.3. Storage Service Implementation (`app/core/storage_service.py`)
    *   Implement the `BaseStorage` abstract base class (or Protocol) and the concrete `LocalFileStorage` and `S3FileStorage` classes.
        *   **`BaseStorage` (ABC):**
            ```python
            # app/core/storage_service.py
            from abc import ABC, abstractmethod
            from typing import BinaryIO, Tuple, Optional, AsyncGenerator
            from pydantic import BaseModel
            from app.core.config import settings # To access settings like expiry seconds
            # ... other necessary imports like uuid, pathlib, mimetypes, aioboto3, aiofiles ...
            import botocore # for S3 client config

            class FileStorageDetails(BaseModel):
                file_key: str
                url: str # For download, or initial info for local upload
                storage_backend: str
                bucket_name: Optional[str] = None
                content_type: Optional[str] = None
                size: Optional[int] = None # Could be populated after successful save

            class PresignedUploadParts(BaseModel): # For S3 direct uploads
                url: str
                fields: Optional[dict] = None # For POST policy uploads
                file_key: str # The key the client should confirm after upload

            class BaseStorage(ABC):
                @abstractmethod
                async def save_proxied_file(self, file_obj: BinaryIO, filename: str, content_type: Optional[str] = None, path_prefix: str = "uploads") -> FileStorageDetails:
                    """Saves a file when the server is proxying the upload."""
                    pass

                @abstractmethod
                async def delete_file(self, file_key: str) -> None:
                    pass

                @abstractmethod
                async def get_download_url(self, file_key: str, filename_for_disposition: Optional[str] = None, expires_in: Optional[int] = None) -> str:
                    """Generates a URL to download the file. Can be pre-signed for cloud."""
                    pass

                @abstractmethod
                async def get_presigned_upload_url(self, filename: str, content_type: Optional[str] = None, path_prefix: str = "uploads", expires_in: Optional[int] = None) -> PresignedUploadParts:
                    """Generates a pre-signed URL for direct client upload (primarily for cloud)."""
                    pass

                @abstractmethod
                async def get_file_stream(self, file_key: str) -> AsyncGenerator[bytes, None]:
                    """Streams a file's content (e.g., for server-side processing)."""
                    pass

                @abstractmethod
                async def file_exists(self, file_key: str) -> bool:
                    """Checks if a file exists at the given key."""
                    pass

                def _generate_file_key(self, path_prefix: str, filename: str) -> str:
                    from pathlib import Path
                    import uuid
                    ext = Path(filename).suffix.lower()
                    return f"{path_prefix.strip('/')}/{uuid.uuid4()}{ext}"
            ```
        *   **`LocalFileStorage` Implementation:**
            *   `__init__(self, media_root: str, media_url_prefix: str)`
            *   `save_proxied_file`: Uses `aiofiles` to write to `media_root`. Generates URL based on `media_url_prefix`.
            *   `delete_file`: Uses `pathlib.Path.unlink()`.
            *   `get_download_url`: Returns static URL: `{media_url_prefix}/{file_key}`.
            *   `get_presigned_upload_url`: For local, this is less relevant for direct PUT. It might return a conceptual target path or an API endpoint the client should POST to for proxied upload. For simplicity, it could raise `NotImplementedError` or signal that direct upload is via a specific API endpoint.
            *   `get_file_stream`: Uses `aiofiles.open` to stream.
            *   `file_exists`: Uses `pathlib.Path.exists()`.
        *   **`S3FileStorage` Implementation:**
            *   `__init__`: Initializes `aioboto3.Session()` and configures S3 client parameters from `settings` (bucket, region, endpoint, etc.).
            *   `save_proxied_file`: Uses `s3_client.upload_fileobj()`.
            *   `delete_file`: Uses `s3_client.delete_object()`.
            *   `get_download_url`: Uses `s3_client.generate_presigned_url('get_object', ...)`.
            *   `get_presigned_upload_url`: Uses `s3_client.generate_presigned_url('put_object', ...)` or `generate_presigned_post(...)`.
            *   `get_file_stream`: Uses `s3_client.get_object()` and streams its `StreamingBody`.
            *   `file_exists`: Uses `s3_client.head_object()`.
        *   **Factory Function `get_storage_service()`:**
            ```python
            # (at the end of app/core/storage_service.py)
            # _storage_instance: Optional[BaseStorage] = None # Singleton instance

            # def get_storage_service() -> BaseStorage:
            #     global _storage_instance
            #     if _storage_instance is None:
            #         if settings.FILE_STORAGE_BACKEND == "s3":
            #             _storage_instance = S3FileStorage()
            #         elif settings.FILE_STORAGE_BACKEND == "local":
            #             _storage_instance = LocalFileStorage(
            #                 media_root=settings.LOCAL_MEDIA_ROOT,
            #                 media_url_prefix=settings.LOCAL_MEDIA_URL_PREFIX
            #             )
            #         else:
            #             raise ValueError(f"Unsupported file storage backend: {settings.FILE_STORAGE_BACKEND}")
            #     return _storage_instance
            ```
            *This singleton approach is simple. For testing or more complex scenarios, a FastAPI dependency that creates/provides the service might be preferred for easier overriding.*

    ### 10.4. `StoredFile` SQLAlchemy Model Definition
    *   Create the `StoredFile` model (e.g., in `app/features/files/models.py` or a common models file).
        ```python
        # from sqlalchemy import Column, Integer, String, DateTime, Boolean, BigInteger, ForeignKey, func
        # from sqlalchemy.orm import Mapped, mapped_column, relationship
        # from app.core.db import Base
        # from typing import Optional

        # class StoredFile(Base):
        #     __tablename__ = "stored_files"
        #     id: Mapped[int] = mapped_column(primary_key=True)
        #     file_key: Mapped[str] = mapped_column(String(1024), unique=True, index=True, comment="Path/key in the storage backend")
        #     original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
        #     content_type: Mapped[Optional[str]] = mapped_column(String(100))
        #     size: Mapped[Optional[int]] = mapped_column(BigInteger) # Size in bytes
        #     storage_backend: Mapped[str] = mapped_column(String(50), comment="e.g., 'local', 's3'")
        #     bucket_name: Mapped[Optional[str]] = mapped_column(String(255), comment="For cloud storage")
        #     # uploaded_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id")) # Example FK
        #     # organization_id: Mapped[Optional[int]] = mapped_column(ForeignKey("organizations.id")) # Example FK
        #     created_at: Mapped[datetime] = mapped_column(server_default=func.now())
        #     # Add relationships if files are directly tied to other specific models, or use a linking table.
        ```

    ### 10.5. FastAPI Static File Serving (for Local Backend Development)
    *   In `app/main.py`, conditionally mount `StaticFiles` if using local storage:
        ```python
        # from fastapi.staticfiles import StaticFiles
        # from app.core.config import settings

        # if settings.FILE_STORAGE_BACKEND == "local":
        #     app.mount(
        #         settings.LOCAL_MEDIA_URL_PREFIX.strip('/'), # Ensure no leading slash for mount path
        #         StaticFiles(directory=settings.LOCAL_MEDIA_ROOT),
        #         name="media_files"
        #     )
        ```

    ### 10.6. Docker Compose Services (Local Development)
    *   Ensure `docker-compose.yml` includes services for:
        *   PostgreSQL
        *   Redis
        *   Elasticsearch (if file search is active locally)
        *   MinIO (if testing S3 backend locally):
            ```yaml
            # services:
            #   minio:
            #     image: minio/minio:RELEASE.2023-03-20T20-16-18Z
            #     ports:
            #       - "9000:9000" # API
            #       - "9001:9001" # Console
            #     volumes:
            #       - minio_data:/data
            #     environment:
            #       MINIO_ROOT_USER: minioadmin # Corresponds to AWS_ACCESS_KEY_ID in .env
            #       MINIO_ROOT_PASSWORD: minioadmin # Corresponds to AWS_SECRET_ACCESS_KEY in .env
            #     command: server /data --console-address ":9001"
            # volumes:
            #   minio_data:
            ```
            *   The application's `.env` would then set `AWS_S3_ENDPOINT_URL=http://minio:9000` (if app runs in same Docker network) or `http://localhost:9000` (if app runs on host and accesses MinIO port). The bucket needs to be created in MinIO (manually or via script).

## 11. Integration & Usage Patterns

    This section describes how feature modules will interact with the file storage system.

    ### 11.1. Defining `StoredFile` Relationships
    *   SQLAlchemy models that own files will have a relationship to `StoredFile`.
        ```python
        # class Product(Base):
        #     # ...
        #     product_image_id: Mapped[Optional[int]] = mapped_column(ForeignKey("stored_files.id"))
        #     product_image: Mapped[Optional["StoredFile"]] = relationship(lazy="selectin")
        ```

    ### 11.2. Pydantic Schemas for File Information
    *   Define Pydantic schemas for representing file information in API responses.
        ```python
        # app/features/files/schemas.py (or a common schema file)
        # class StoredFileRead(BaseModel):
        #     id: int
        #     file_key: str
        #     original_filename: str
        #     content_type: Optional[str] = None
        #     size: Optional[int] = None
        #     download_url: Optional[str] = None # To be populated by service
        #     model_config = {"from_attributes": True}
        ```

    ### 11.3. File Upload API Endpoints (`app/features/files/router.py` - Conceptual)
    *   A dedicated `APIRouter` for file operations.
    *   **Initiate Upload (Client gets pre-signed URL for S3 / prepares for local):**
        ```python
        # @file_router.post("/initiate-upload/", response_model=PresignedUploadParts)
        # async def initiate_file_upload(
        #     filename: str = Form(...),
        #     content_type: Optional[str] = Form(None),
        #     # ... other metadata like intended parent_entity_id ...
        #     storage: BaseStorage = Depends(get_storage_service), # Injected storage service
        #     # current_user: User = Depends(get_current_active_user) # For permissions
        # ):
        #     # Perform permission checks for uploading
        #     # Generate a path prefix if needed (e.g., based on org_id/user_id)
        #     # path_prefix = f"orgs/{current_user.organization_id}/users/{current_user.id}"
        #     return await storage.get_presigned_upload_url(filename, content_type) #, path_prefix=path_prefix)
        ```
    *   **Confirm S3 Upload & Create `StoredFile` Record:**
        ```python
        # class ConfirmUploadSchema(BaseModel):
        #    file_key: str
        #    original_filename: str
        #    content_type: str
        #    size: int
        #    # ... fields to link to parent entity ...

        # @file_router.post("/confirm-upload/", response_model=StoredFileRead)
        # async def confirm_s3_upload(
        #     payload: ConfirmUploadSchema,
        #     storage: BaseStorage = Depends(get_storage_service),
        #     db: AsyncSession = Depends(get_db_session),
        #     # current_user: User = Depends(get_current_active_user)
        # ):
        #     if settings.FILE_STORAGE_BACKEND != "s3": # Or check based on file_key prefix
        #         raise HTTPException(status_code=400, detail="This endpoint is for S3 uploads.")
        #
        #     # Optional: Verify file actually exists in S3 at payload.file_key
        #     # if not await storage.file_exists(payload.file_key):
        #     #     raise HTTPException(status_code=400, detail="File not found at specified key.")
        #
        #     # Create StoredFile record in DB
        #     db_stored_file = StoredFile(
        #         file_key=payload.file_key,
        #         original_filename=payload.original_filename,
        #         # ... populate other fields ...
        #         storage_backend="s3", # Or derive from config
        #         bucket_name=settings.AWS_S3_BUCKET_NAME
        #     )
        #     # ... associate with parent entity, set uploader, org ...
        #     db.add(db_stored_file)
        #     await db.flush() # To get ID
        #
        #     # Trigger async task for Elasticsearch indexing
        #     # index_file_metadata_task.delay(db_stored_file.id)
        #
        #     # Populate download_url for response (usually done in a service or schema resolver)
        #     # response_data = StoredFileRead.from_orm(db_stored_file)
        #     # response_data.download_url = await storage.get_download_url(db_stored_file.file_key)
        #     # return response_data
        #     return await service.get_stored_file_response(db, storage, db_stored_file.id) # Example service call
        ```
    *   **Handle Direct Local Upload & Create `StoredFile` Record:**
        ```python
        # from fastapi import UploadFile, File

        # @file_router.post("/upload-local/", response_model=StoredFileRead)
        # async def upload_local_file_direct(
        #     file: UploadFile = File(...),
        #     # ... other metadata ...
        #     storage: BaseStorage = Depends(get_storage_service),
        #     db: AsyncSession = Depends(get_db_session),
        #     # current_user: User = Depends(get_current_active_user)
        # ):
        #     if settings.FILE_STORAGE_BACKEND != "local":
        #         raise HTTPException(status_code=400, detail="Local file uploads are not enabled.")
        #
        #     # path_prefix = f"orgs/{current_user.organization_id}/users/{current_user.id}"
        #     storage_details = await storage.save_proxied_file(
        #         file.file, file.filename, file.content_type # path_prefix=path_prefix
        #     )
        #
        #     # Create StoredFile record
        #     # ... similar to confirm_s3_upload ...
        #     # index_file_metadata_task.delay(db_stored_file.id)
        #     # return await service.get_stored_file_response(db, storage, db_stored_file.id)
        ```

    ### 11.4. Generating Download URLs in Responses
    *   When an API returns data for an entity that has an associated file (e.g., `ProductRead` includes `product_image_info: Optional[StoredFileRead]`), the `StoredFileRead.download_url` field needs to be populated.
    *   This is typically done in the service layer that prepares the response data, or via a Pydantic `@computed_field` (if the storage service can be accessed easily there, though service layer is cleaner).
        ```python
        # In a service function returning a Product with its image
        # async def get_product_for_api(product_orm: models.Product, storage: BaseStorage) -> schemas.ProductRead:
        #     # ... map product_orm to schemas.ProductRead ...
        #     # if product_orm.product_image: # Assuming product_image is a StoredFile ORM instance
        #     #    image_info = schemas.StoredFileRead.from_orm(product_orm.product_image)
        #     #    image_info.download_url = await storage.get_download_url(product_orm.product_image.file_key)
        #     #    product_read_schema.product_image_info = image_info
        #     return product_read_schema
        ```

    ### 11.5. Deleting Files
    *   When a `StoredFile` record is deleted (or its parent entity is deleted with cascading):
        1.  An SQLAlchemy event listener (`after_delete` on `StoredFile`) or explicit service logic triggers an asynchronous Celery task.
        2.  The Celery task receives `file_key`, `storage_backend`, `bucket_name`.
        3.  The task uses the appropriate storage service (`LocalFileStorage` or `S3FileStorage`) to delete the actual file object from the storage.
        4.  The task also deletes the corresponding document from Elasticsearch.

