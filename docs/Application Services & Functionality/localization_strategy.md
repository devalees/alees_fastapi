# Localization (i18n/L10n) Strategy (FastAPI Edition - Content Focus)

## 1. Overview

    * Purpose: To define the strategy for localizing specific model *content* (data within entity instances) in the FastAPI-based ERP system.
    * Scope: Model Content/Data Localization for designated character fields, managed via dedicated translation APIs. Also covers backend responsibilities for locale-aware formatting (if any) and timezone handling.
    * Out of Scope (Handled by Frontend): Static UI String Localization (e.g., button text), UI Field Label Localization (e.g., display names of form fields like "Product Type").
    * Goal: Allow specific database content fields to be stored and retrieved in multiple languages via a clear API structure, ensuring data integrity.

## 2. Core Principles

    * Primary Language for Core Data: Main entity models store primary textual content in the organization's `primary_language_code`.
    * Dedicated Translation Management APIs: Translations for model content are managed as separate resources.
    * Explicit Language Context: API requests specify target language for localized data or translation operations.
    * Fallback to Primary Language: If a translation is not available, content from the primary language is used.
    * Standard Formats & UTF-8.
    * UTC for Timestamps.

## 3. Configuration (`app/core/config.py` - Pydantic Settings)

    * `SUPPORTED_LANGUAGES: List[tuple[str, str]]` (e.g., `[("en", "English"), ("fr", "Français")]`).
    * `DEFAULT_SYSTEM_LANGUAGE_CODE: str` (e.g., `"en"`).
    * **Organization-Specific (if applicable, stored in `Organization` model):**
        * `primary_language_code: str`
        * `active_translation_languages: List[str]` (languages other than primary, active for translation).
    * **Discovering Translatable Fields:**
        * Models inherit a marker mixin (e.g., `TranslatableContentMixin` in `app/core/i18n_base.py`).
        * SQLAlchemy columns `String` or `Text` marked with `info={'translatable': True}` are eligible for content translation.

## 4. Language Detection for API Requests (Content Localization - Strategic Overview)

    * FastAPI dependency (e.g., `get_current_request_language`) determines active language from `lang` query param, user profile, `Accept-Language` header, org primary, or system default.

## 5. Model Content/Data Localization (Strategic Overview - Separate Tables per Entity)

    * Main entity fields store primary language data.
    * A separate table (e.g., `ProductTextTranslation`) per translatable entity type stores translations for other active languages for designated fields.
    * Translations are managed via distinct API endpoints.

## 6. Formatting & Timezone Handling (Strategic Overview)

    * **Formatting (L10n):** `Babel` library for any backend-generated human-readable strings (e.g., emails). APIs return raw data types primarily.
    * **Timezones:** Store datetimes as UTC. API accepts/returns ISO 8601 with UTC. User-specific conversions if needed by business logic.

## 7. General Setup Implementation Details (Model Content Localization)

    This section details the setup for the backend's model content translation capabilities.

    ### 7.1. Library Installation
    *   `Babel>=2.12.0,<2.14.0` (or latest stable) in `requirements/base.txt` (for any server-side formatting).
    *   SQLAlchemy, Pydantic, FastAPI are core.

    ### 7.2. Core i18n Base (`app/core/i18n_base.py`)
    *   Define the marker mixin.
        ```python
        # app/core/i18n_base.py
        class TranslatableContentMixin:
            """Marker mixin for SQLAlchemy models that have translatable content fields."""
            pass
        ```

    ### 7.3. Pydantic Settings (`app/core/config.py`)
    *   Ensure `SUPPORTED_LANGUAGES` and `DEFAULT_SYSTEM_LANGUAGE_CODE` are defined.
        ```python
        # In Settings class:
        # SUPPORTED_LANGUAGES: List[Tuple[str, str]] = [("en", "English"), ("fr", "Français"), ("es", "Español")]
        # DEFAULT_SYSTEM_LANGUAGE_CODE: str = "en"
        # ORGANIZATION_PRIMARY_LANGUAGE_DEFAULT: str = "en" # Default for new orgs
        # ORGANIZATION_ACTIVE_TRANSLATION_LANGUAGES_DEFAULT: List[str] = ["es", "fr"] # Default for new orgs
        ```
    *   Organization-level language settings would be fields on your `Organization` SQLAlchemy model.

    ### 7.4. SQLAlchemy Model Structure
    *   **Main Entity Model (Example `Product`):**
        ```python
        # app/features/products/models.py
        from sqlalchemy import String, Text, ForeignKey # Add other necessary imports
        from sqlalchemy.orm import Mapped, mapped_column, relationship
        from typing import Optional, List
        from app.core.db import Base
        from app.core.i18n_base import TranslatableContentMixin # Import marker

        class ProductTextTranslation(Base): # Define this first or use forward references
            __tablename__ = "product_text_translations"
            parent_product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), primary_key=True)
            language_code: Mapped[str] = mapped_column(String(10), primary_key=True)
            field_name: Mapped[str] = mapped_column(String(100), primary_key=True)
            translated_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
            parent_product: Mapped["Product"] = relationship(back_populates="text_translations")

        class Product(Base, TranslatableContentMixin):
            __tablename__ = "products"
            id: Mapped[int] = mapped_column(primary_key=True, index=True)
            sku: Mapped[str] = mapped_column(String(100), unique=True, index=True) # Non-translatable
            name: Mapped[str] = mapped_column(String(255), info={'translatable': True}) # Primary lang text
            description: Mapped[Optional[str]] = mapped_column(Text, nullable=True, info={'translatable': True}) # Primary lang

            text_translations: Mapped[List["ProductTextTranslation"]] = relationship(
                back_populates="parent_product",
                cascade="all, delete-orphan",
                lazy="selectin", # Eager load translations when Product is loaded
                # primaryjoin="and_(Product.id == ProductTextTranslation.parent_product_id)" # Explicit join if needed
            )
        ```
        *Repeat the `...TextTranslation` pattern for each model type needing content translation (e.g., `CategoryTextTranslation`).*

    ### 7.5. Alembic Migrations
    *   After defining models, run `alembic revision --autogenerate -m "add_product_and_translations_tables"` and `alembic upgrade head`. Review generated scripts.

    ### 7.6. Core Language Detection Dependency (`app/core/dependencies.py`)
        ```python
        # app/core/dependencies.py
        from fastapi import Request, Query, Depends, HTTPException, status
        from typing import Optional, List
        from app.core.config import settings
        # from app.features.organizations.models import Organization # Assuming you have this
        # from app.features.users.schemas import UserRead # Assuming current_user context

        # Placeholder for organization fetching logic
        # async def get_request_organization_from_path_or_user(
        #     # organization_id: Optional[int] = Path(None), # if org_id is in path
        #     # current_user: UserRead = Depends(get_optional_current_user) # Assuming this gives user with org info
        # ) -> Optional[Organization]:
        #     # Logic to determine the relevant organization for the request
        #     # This is highly dependent on your multi-tenancy strategy
        #     return None # Replace with actual logic

        async def get_request_language_code(
            request: Request,
            lang: Optional[str] = Query(None, description="Target language code for response localization (e.g., 'en', 'fr')."),
            # organization: Optional[Organization] = Depends(get_request_organization_from_path_or_user),
            # current_user: Optional[UserRead] = Depends(get_optional_current_user) # If user preference is used
        ) -> str:
            # 1. Query parameter
            if lang and lang in [lc[0] for lc in settings.SUPPORTED_LANGUAGES]:
                return lang

            # 2. User profile preference (Example - needs User model and service)
            # if current_user and current_user.preferred_language_code and \
            #    current_user.preferred_language_code in [lc[0] for lc in settings.SUPPORTED_LANGUAGES]:
            #     return current_user.preferred_language_code

            # 3. Accept-Language header
            accept_language = request.headers.get("accept-language")
            if accept_language:
                # Simple parsing: take the first preferred language
                # More robust parsing would handle weights (q-values)
                preferred_langs = [ln.split(';')[0].strip().lower() for ln in accept_language.split(',')]
                for preferred_lang in preferred_langs:
                    # Check full code (e.g., "fr-CA") or base (e.g., "fr")
                    if preferred_lang in [lc[0] for lc in settings.SUPPORTED_LANGUAGES]:
                        return preferred_lang
                    base_lang = preferred_lang.split('-')[0]
                    if base_lang in [lc[0] for lc in settings.SUPPORTED_LANGUAGES]:
                        return base_lang

            # 4. Organization's primary language (Example)
            # if organization and organization.primary_language_code and \
            #    organization.primary_language_code in [lc[0] for lc in settings.SUPPORTED_LANGUAGES]:
            #     return organization.primary_language_code

            # 5. System default
            return settings.DEFAULT_SYSTEM_LANGUAGE_CODE
        ```

    ### 7.7. Core Translation Service (`app/core/i18n_services/content_translation_service.py`)
    *   This service will contain the logic for fetching and saving translations.
        ```python
        # app/core/i18n_services/content_translation_service.py
        from sqlalchemy.ext.asyncio import AsyncSession
        from sqlalchemy.future import select
        from typing import Any, Dict, List, Optional, Type
        from app.core.db import Base # For type hinting ORM models
        from app.core.config import settings
        import logging

        logger = logging.getLogger(__name__)

        # This function needs to know the specific TranslationTableModel for an entity_type
        # This requires a mapping or a convention (e.g., Product -> ProductTextTranslation)
        # For this example, let's assume we pass the TranslationTableModel directly

        async def get_localized_value(
            db: AsyncSession,
            parent_instance: Base, # e.g., a Product instance
            field_name: str,
            requested_lang_code: str,
            TranslationTableModel: Type[Base], # e.g., models.ProductTextTranslation
            parent_id_field_name: str = "parent_product_id" # FK field name on TranslationTableModel
        ) -> Any:
            """
            Gets the translated value for a field, falling back to primary language.
            Assumes parent_instance has the primary language value as a direct attribute.
            """
            primary_value = getattr(parent_instance, field_name, None)
            org_primary_lang = getattr(parent_instance.organization, "primary_language_code", settings.DEFAULT_SYSTEM_LANGUAGE_CODE) \
                                if hasattr(parent_instance, "organization") and parent_instance.organization else settings.DEFAULT_SYSTEM_LANGUAGE_CODE


            if requested_lang_code == org_primary_lang:
                return primary_value

            # Fetch specific translation
            stmt = select(TranslationTableModel).where(
                getattr(TranslationTableModel, parent_id_field_name) == parent_instance.id,
                TranslationTableModel.language_code == requested_lang_code,
                TranslationTableModel.field_name == field_name
            )
            result = await db.execute(stmt)
            translation_record = result.scalar_one_or_none()

            if translation_record and translation_record.translated_value is not None:
                return translation_record.translated_value

            return primary_value # Fallback to primary language value

        async def get_all_translations_for_field(
            db: AsyncSession,
            parent_instance: Base,
            field_name: str,
            active_translation_langs: List[str], # Org's active translation languages
            TranslationTableModel: Type[Base],
            parent_id_field_name: str = "parent_product_id"
        ) -> Dict[str, Optional[str]]:
            """
            Gets all active translations for a specific field of a parent instance.
            """
            translations = {}
            stmt = select(TranslationTableModel).where(
                getattr(TranslationTableModel, parent_id_field_name) == parent_instance.id,
                TranslationTableModel.field_name == field_name,
                TranslationTableModel.language_code.in_(active_translation_langs)
            )
            result = await db.execute(stmt)
            for tr_record in result.scalars().all():
                translations[tr_record.language_code] = tr_record.translated_value

            # Fill in missing active languages with None or primary value as placeholder
            for lang_code in active_translation_langs:
                if lang_code not in translations:
                    translations[lang_code] = None # Or getattr(parent_instance, field_name) to show primary
            return translations


        async def upsert_field_translations(
            db: AsyncSession,
            parent_instance: Base, # e.g., Product instance
            language_code_to_update: str,
            field_translations_payload: Dict[str, Optional[str]], # {"name": "Texte FR", "description": null}
            TranslationTableModel: Type[Base],
            parent_id_field_name: str = "parent_product_id"
        ):
            """
            Updates or creates translation records for multiple fields of a parent entity for a specific language.
            Deletes translation if value is None.
            """
            # First, identify which fields are actually translatable for this parent_instance type
            translatable_field_names = [
                col.name for col in parent_instance.__table__.columns
                if col.info.get('translatable', False)
            ]

            for field_name, translated_value in field_translations_payload.items():
                if field_name not in translatable_field_names:
                    logger.warning(f"Attempt to translate non-translatable field '{field_name}' for {parent_instance.__tablename__}. Skipping.")
                    continue

                # Check if translation record exists
                stmt_select = select(TranslationTableModel).where(
                    getattr(TranslationTableModel, parent_id_field_name) == parent_instance.id,
                    TranslationTableModel.language_code == language_code_to_update,
                    TranslationTableModel.field_name == field_name
                )
                existing_translation = (await db.execute(stmt_select)).scalar_one_or_none()

                if translated_value is not None and translated_value.strip() != "": # Save or update
                    if existing_translation:
                        existing_translation.translated_value = translated_value
                        db.add(existing_translation)
                    else:
                        new_translation = TranslationTableModel(
                            **{parent_id_field_name: parent_instance.id},
                            language_code=language_code_to_update,
                            field_name=field_name,
                            translated_value=translated_value
                        )
                        db.add(new_translation)
                elif existing_translation: # Delete if new value is None/empty and record exists
                    await db.delete(existing_translation)
            # await db.flush() # Flush changes. Commit is handled by session context manager.
        ```

## 8. Integration & Usage Patterns

    ### 8.1. Main Entity CRUD (Create/Update in Primary Language)
    *   API endpoints for entities (e.g., `POST /api/v1/products/`) accept data for fields (e.g., `name`, `description`) in the organization's `primary_language_code`.
    *   Service functions save this data directly to the main entity's columns.
        ```python
        # app/features/products/services/product_service.py
        # async def create_product(db: AsyncSession, product_in: schemas.ProductCreate, organization_id: int) -> models.Product:
        #     # Assume product_in.name and product_in.description are in primary language
        #     db_product = models.Product(
        #         sku=product_in.sku,
        #         name=product_in.name_default_lang, # From schema adjusted for this strategy
        #         description=product_in.description_default_lang,
        #         price=product_in.price,
        #         organization_id=organization_id # Assuming Product is org-scoped
        #     )
        #     db.add(db_product)
        #     # await db.flush()
        #     # await db.refresh(db_product)
        #     # No automatic creation of XTextTranslation records here.
        #     return db_product
        ```

    ### 8.2. Fetching Localized Entity Data (Main Entity `GET` Endpoints)
    *   `GET /api/v1/products/{product_id}/?lang=fr`
    *   The service function populates the response Pydantic schema (e.g., `ProductRead`) by:
        1.  Fetching the main `Product` ORM object.
        2.  For each field marked `info={'translatable': True}` (e.g., "name"):
            *   Calling `content_translation_service.get_localized_value(db, product_orm, "name", requested_lang_code, models.ProductTextTranslation)`.
        3.  This service function handles the fallback to the primary language value from `product_orm.name` if the specific translation isn't found.
        ```python
        # app/features/products/services/product_service.py
        # async def get_localized_product_for_api(
        #     db: AsyncSession, product_id: int, requested_lang_code: str
        # ) -> Optional[schemas.ProductRead]:
        #     stmt = select(models.Product).options(selectinload(models.Product.text_translations)).filter(models.Product.id == product_id)
        #     product_orm = (await db.execute(stmt)).scalar_one_or_none()
        #     if not product_orm: return None

        #     # Get org's primary language (example, replace with actual logic)
        #     # org_primary_lang = await get_org_primary_language(db, product_orm.organization_id)
        #     org_primary_lang = settings.DEFAULT_SYSTEM_LANGUAGE_CODE # Simplified

        #     data_for_schema = {"id": product_orm.id, "sku": product_orm.sku} # Non-translatable

        #     for col in product_orm.__table__.columns: # Iterate through model columns
        #         if col.info.get('translatable', False):
        #             field_name = col.name
        #             primary_value = getattr(product_orm, field_name)
        #             translated_value = primary_value # Default to primary

        #             if requested_lang_code != org_primary_lang:
        #                 found_translation = False
        #                 for tr in product_orm.text_translations: # text_translations already eager loaded
        #                     if tr.language_code == requested_lang_code and tr.field_name == field_name:
        #                         translated_value = tr.translated_value
        #                         found_translation = True
        #                         break
        #             data_for_schema[field_name] = translated_value
        #     return schemas.ProductRead(**data_for_schema)
        ```

    ### 8.3. Managing Content Translations (Dedicated API - `app/features/content_translations/router.py`)
    *   **Get Translatable Data Structure for an Instance:**
        *   `GET /api/v1/content-translations/{entity_type}/{entity_id}/`
        *   The service for this endpoint iterates `info={'translatable': True}` fields of the parent entity. For each field, it gets the `primary_value` (from parent) and then calls `content_translation_service.get_all_translations_for_field(...)` to populate existing translations for active languages.
    *   **Update/Save Translations for an Instance:**
        *   `PUT /api/v1/content-translations/{entity_type}/{entity_id}/`
        *   Request body includes `language_code` and `field_translations: Dict[field_name, translated_text]`.
        *   The service calls `content_translation_service.upsert_field_translations(...)`.
        ```python
        # app/features/content_translations/router.py (Conceptual)
        # from .services import translation_management_service
        # from .schemas import EntityTranslationUpdateRequest, EntityTranslationResponse

        # @router.get("/{entity_type}/{entity_id}/", response_model=EntityTranslationResponse)
        # async def get_entity_translations_for_management(entity_type: str, entity_id: int, ...):
        #     # return await translation_management_service.get_translatable_structure(
        #     #    db, entity_type, entity_id, organization.active_translation_languages, organization.primary_language_code
        #     # )
        #     pass

        # @router.put("/{entity_type}/{entity_id}/", response_model=StatusResponseSchema) # Simple status response
        # async def update_entity_translations(
        #     entity_type: str, entity_id: int, payload: EntityTranslationUpdateRequest, ...
        # ):
        #     # await translation_management_service.save_translations(
        #     #    db, entity_type, entity_id, payload.language_code, payload.field_translations
        #     # )
        #     # return {"status": "success", "message": "Translations updated."}
        #     pass
        ```

    ### 8.4. Formatting Dates/Numbers (Server-Side via Babel - If Needed)
    *   If the backend generates human-readable reports or emails with localized formatting:
        ```python
        # from babel.numbers import format_currency
        # from babel.dates import format_datetime
        # from app.core.dependencies import get_request_language_code # To get 'fr_FR' or 'en_US' style locale

        # async def generate_invoice_text(amount: Decimal, currency_code: str, due_date: datetime, locale_str: str):
        #     formatted_amount = format_currency(amount, currency_code, locale=locale_str)
        #     formatted_due_date = format_datetime(due_date, format="long", locale=locale_str)
        #     return f"Please pay {formatted_amount} by {formatted_due_date}."
        ```
