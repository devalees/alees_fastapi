# Email Service Integration Strategy

## 1. Overview

- **Purpose**: To define the strategy and implementation approach for sending transactional and notification emails from the FastAPI-based ERP application.
- **Scope**: Covers library selection for sending emails, configuration, integration with asynchronous task processing (Celery), basic templating considerations, and security for email credentials.
- **Goal**: Reliable, configurable, and maintainable email sending capability for various application needs (e.g., user registration, password resets, notifications, alerts).

## 2. Core Principles

- **Asynchronous Sending (Primary)**: Most emails, especially bulk or non-critical transactional ones, will be sent asynchronously via Celery tasks to avoid blocking API responses and to handle retries.
- **Configurability**: Email service provider details (SMTP server, API keys for transactional email services) must be configurable via Pydantic Settings.
- **Security**: Email credentials must be managed securely via the secrets management strategy.
- **Templating**: Use a simple templating mechanism for email bodies if HTML emails or dynamic content are required.
- **Reliability**: Leverage Celery's retry mechanisms for email sending tasks.
- **Testability**: Email sending should be easily mockable or divertable during testing.

## 3. Chosen Technologies & Libraries

- **Email Sending Library (Python):**
  - **Recommendation:** **`python-multipart`** (already a FastAPI dependency for `UploadFile`, can be used for constructing email messages) and Python's built-in **`smtplib`** (for basic SMTP) or **`aiohttp` / `httpx`** (if using an HTTP-based transactional email service API like SendGrid, Mailgun, Postmark, AWS SES API).
  - **Alternative (Higher-level libraries):** Libraries like `fastapi-mail` (builds on `python-multipart` and `aiosmtplib`) can simplify SMTP operations and templating with FastAPI.
  - **Decision:** Let's plan for using an **HTTP-based Transactional Email Service (TES)** like AWS SES, SendGrid, or Mailgun. This is generally more robust and scalable for application emails than direct SMTP from application servers. We will use **`httpx`** (which should already be in `requirements/test.txt` for `TestClient`, promote to `base.txt` if not already) for making API calls to the TES.
- **Asynchronous Task Queue:** Celery (as defined in `asynchronous_celery_strategy.md`).
- **Templating (Optional, for HTML emails):** Jinja2.
  - Add to `requirements/base.txt`: `Jinja2>=3.0,<4.0`.
  - Add `httpx>=0.24.0,<0.26.0` to `requirements/base.txt` if not already there.

## 4. General Setup Implementation Details

    ### 4.1. Library Installation
    *   Ensure `httpx` and `Jinja2` (if using templates) are in `requirements/base.txt`.

    ### 4.2. Pydantic Settings (`app/core/config.py`)
    *   Define settings for the chosen Transactional Email Service (TES). Example for a generic HTTP API based TES:
        ```python
        # In Settings class (app/core/config.py)
        # ...
        EMAIL_BACKEND_TYPE: str = "CONSOLE" # Options: "TES_API", "SMTP", "CONSOLE", "FILE" (for dev/test)

        # For Transactional Email Service (TES) via API (e.g., SendGrid, Mailgun, Postmark, AWS SES API)
        TES_API_URL: Optional[str] = None # e.g., "https://api.sendgrid.com/v3/mail/send"
        TES_API_KEY: Optional[str] = None # From secrets manager
        DEFAULT_FROM_EMAIL: str = "noreply@erp.example.com"
        DEFAULT_FROM_NAME: str = "ERP System"

        # For SMTP (if EMAIL_BACKEND_TYPE is "SMTP") - Less recommended for production scale
        # SMTP_HOST: Optional[str] = None
        # SMTP_PORT: Optional[int] = 587
        # SMTP_USERNAME: Optional[str] = None # From secrets
        # SMTP_PASSWORD: Optional[str] = None # From secrets
        # SMTP_USE_TLS: bool = True

        # For FILE backend (development - writes emails to files)
        # EMAIL_FILE_PATH: str = "/tmp/erp_emails" # Ensure this path is writable

        # For CONSOLE backend (development - prints emails to console)
        # (No specific settings needed)
        ```
    *   `TES_API_KEY` and `SMTP_PASSWORD`/`SMTP_USERNAME` must be loaded from environment variables populated by the secrets manager.

    ### 4.3. Email Service Wrapper (`app/common_services/email/email_service.py`)
    *   Create a service to abstract email sending logic.
        ```python
        # app/common_services/email/email_service.py
        import httpx
        import logging
        from typing import List, Optional, Dict, Any
        from pydantic import EmailStr, BaseModel
        from app.core.config import settings
        # from jinja2 import Environment, FileSystemLoader, select_autoescape # If using Jinja2

        logger = logging.getLogger(__name__)

        # if settings.EMAIL_BACKEND_TYPE != "CONSOLE" and settings.EMAIL_BACKEND_TYPE != "FILE": # Only init if needed
        #    template_env = Environment(
        #        loader=FileSystemLoader("app/common_services/email/templates"), # Path to email templates
        #        autoescape=select_autoescape(['html', 'xml'])
        #    )

        class EmailRecipient(BaseModel):
            email: EmailStr
            name: Optional[str] = None

        class EmailMessage(BaseModel):
            to_recipients: List[EmailRecipient]
            subject: str
            html_body: Optional[str] = None
            text_body: Optional[str] = None
            from_email: EmailStr = settings.DEFAULT_FROM_EMAIL
            from_name: Optional[str] = settings.DEFAULT_FROM_NAME
            # cc: Optional[List[EmailRecipient]] = None
            # bcc: Optional[List[EmailRecipient]] = None
            # attachments: Optional[List[Any]] = None # More complex structure for attachments

        async def send_email_via_tes_api(message: EmailMessage) -> bool:
            if not settings.TES_API_URL or not settings.TES_API_KEY:
                logger.error("Transactional Email Service (TES) API URL or Key not configured.")
                return False

            # This is a generic example; structure will depend on the specific TES provider
            # Example payload structure (highly dependent on provider like SendGrid, Mailgun, etc.)
            payload = {
                "personalizations": [{"to": [{"email": recip.email, "name": recip.name} for recip in message.to_recipients]}],
                "from": {"email": message.from_email, "name": message.from_name},
                "subject": message.subject,
                "content": []
            }
            if message.text_body:
                payload["content"].append({"type": "text/plain", "value": message.text_body})
            if message.html_body:
                payload["content"].append({"type": "text/html", "value": message.html_body})

            headers = {
                "Authorization": f"Bearer {settings.TES_API_KEY}", # Or other auth method
                "Content-Type": "application/json"
            }
            async with httpx.AsyncClient() as client:
                try:
                    response = await client.post(settings.TES_API_URL, json=payload, headers=headers)
                    response.raise_for_status() # Raises HTTPStatusError for 4xx/5xx
                    logger.info(f"Email sent successfully to {', '.join([r.email for r in message.to_recipients])} via TES API. Subject: {message.subject}")
                    return True
                except httpx.HTTPStatusError as e:
                    logger.error(f"TES API error sending email: {e.response.status_code} - {e.response.text}", exc_info=True)
                except httpx.RequestError as e:
                    logger.error(f"TES API request error sending email: {e}", exc_info=True)
                return False

        async def send_email_console(message: EmailMessage) -> bool:
            logger.info("--- SENDING EMAIL (CONSOLE BACKEND) ---")
            logger.info(f"From: {message.from_name} <{message.from_email}>")
            logger.info(f"To: {', '.join([f'{r.name}<{r.email}>' if r.name else r.email for r in message.to_recipients])}")
            logger.info(f"Subject: {message.subject}")
            if message.text_body:
                logger.info(f"Text Body:\n{message.text_body}")
            if message.html_body:
                logger.info(f"HTML Body:\n{message.html_body}")
            logger.info("--- END OF EMAIL (CONSOLE BACKEND) ---")
            return True

        # Add send_email_file and send_email_smtp if needed, using aiosmtplib for async SMTP

        async def send_email(
            to_emails: List[EmailStr],
            subject: str,
            html_body: Optional[str] = None,
            text_body: Optional[str] = None,
            to_names: Optional[List[Optional[str]]] = None,
            # template_name: Optional[str] = None, # For Jinja2 templating
            # template_context: Optional[Dict[str, Any]] = None # For Jinja2 templating
        ) -> bool:
            recipients = []
            for i, email_addr in enumerate(to_emails):
                name = to_names[i] if to_names and i < len(to_names) else None
                recipients.append(EmailRecipient(email=email_addr, name=name))

            # if template_name and template_context is not None:
            #     template = template_env.get_template(template_name) # e.g., "welcome_email.html"
            #     html_body = template.render(**template_context)
                # Potentially render a text version too or extract from HTML

            if not text_body and not html_body:
                logger.error("Email has no body content.")
                return False
            if not text_body and html_body: # Simple way to get a text part
                # For more robust HTML to text, use a library
                text_body = "Please view this email in an HTML-compatible client."


            email_msg = EmailMessage(
                to_recipients=recipients,
                subject=subject,
                html_body=html_body,
                text_body=text_body
            )

            if settings.EMAIL_BACKEND_TYPE == "TES_API":
                return await send_email_via_tes_api(email_msg)
            elif settings.EMAIL_BACKEND_TYPE == "CONSOLE":
                return await send_email_console(email_msg)
            # elif settings.EMAIL_BACKEND_TYPE == "SMTP":
            #     return await send_email_smtp(email_msg) # Requires aiosmtplib
            # elif settings.EMAIL_BACKEND_TYPE == "FILE":
            #     return await send_email_file(email_msg) # Requires aiofiles
            else:
                logger.error(f"Unsupported email backend type: {settings.EMAIL_BACKEND_TYPE}")
                return False
        ```
    *   The `EMAIL_BACKEND_TYPE` setting controls behavior:
        *   `"TES_API"`: Uses the configured HTTP API (recommended for prod).
        *   `"SMTP"`: Uses `smtplib` or `aiosmtplib` (less common for direct app sending at scale).
        *   `"CONSOLE"`: Prints email to console (for local development).
        *   `"FILE"`: Writes email content to files in `settings.EMAIL_FILE_PATH` (for local development/testing).

    ### 4.4. Email Templates (Optional - `app/common_services/email/templates/`)
    *   If using Jinja2 for HTML emails, create template files (e.g., `welcome_email.html`, `password_reset.html`) in this directory.
    *   The `email_service.py` would load and render these templates.

## 5. Integration & Usage Patterns

    ### 5.1. Sending Emails Asynchronously via Celery (Primary Method)
    *   Define a Celery task that calls the `email_service.send_email` function.
        ```python
        # app/common_services/email/tasks.py
        from app.core.celery_app import celery_app
        from .email_service import send_email
        from typing import List, Optional, Dict, Any
        from pydantic import EmailStr
        import logging

        logger = logging.getLogger(__name__)

        @celery_app.task(name="email.send_transactional_email", max_retries=3, default_retry_delay=300) # Retry after 5 mins
        async def send_transactional_email_task(
            to_emails: List[EmailStr],
            subject: str,
            html_body: Optional[str] = None,
            text_body: Optional[str] = None,
            to_names: Optional[List[Optional[str]]] = None
            # template_name: Optional[str] = None,
            # template_context: Optional[Dict[str, Any]] = None
        ):
            logger.info(f"Celery task: Attempting to send email. Subject: '{subject}', To: {to_emails}")
            success = await send_email(
                to_emails=to_emails,
                subject=subject,
                html_body=html_body,
                text_body=text_body,
                to_names=to_names
                # template_name=template_name,
                # template_context=template_context
            )
            if not success:
                logger.error(f"Celery task: Failed to send email. Subject: '{subject}', To: {to_emails}. Will retry if attempts left.")
                # Celery will retry automatically based on task decorator settings on exception
                # For non-exception failures from send_email, you might need custom retry logic
                # by raising an exception here if `success` is False.
                raise Exception(f"Email sending failed for subject: {subject}")
            return {"status": "success", "subject": subject, "to": to_emails}
        ```
    *   **Dispatching the task from application code (e.g., a user service after registration):**
        ```python
        # app/features/users/service.py
        # from app.common_services.email.tasks import send_transactional_email_task

        # async def register_new_user(db: AsyncSession, user_in: UserCreateSchema):
        #     # ... user creation logic ...
        #     # new_user = ...
        #     send_transactional_email_task.delay(
        #         to_emails=[new_user.email],
        #         subject="Welcome to ERP System!",
        #         html_body=f"<p>Hi {new_user.full_name}, welcome!</p>", # Or use template_name/context
        #         to_names=[new_user.full_name]
        #     )
        #     return new_user
        ```

    ### 5.2. Sending Emails Directly from FastAPI (Use Sparingly - e.g., `BackgroundTasks`)
    *   For very simple, non-critical emails where immediate dispatch after a response is acceptable and a slight chance of failure (if app crashes) is tolerable.
        ```python
        # app/features/some_feature/router.py
        # from fastapi import BackgroundTasks
        # from app.common_services.email.email_service import send_email

        # @router.post("/submit-feedback")
        # async def submit_feedback(feedback_text: str, background_tasks: BackgroundTasks):
        #     # ... save feedback ...
        #     background_tasks.add_task(
        #         send_email,
        #         to_emails=["admin@erp.example.com"],
        #         subject="New Feedback Submitted",
        #         text_body=f"Feedback received: {feedback_text}"
        #     )
        #     return {"message": "Feedback submitted. Admin will be notified."}
        ```

    ### 5.3. Using Email Templates
    *   Pass `template_name` (e.g., `"password_reset.html"`) and `template_context` (a dict for template variables) to the `send_email` service function (or the Celery task wrapper). The service will render the Jinja2 template.

## 6. Testing

- **During most tests (unit, integration):**
  - Set `settings.EMAIL_BACKEND_TYPE = "CONSOLE"` or `"FILE"` via test configuration/environment variables.
  - This prevents actual emails from being sent.
  - For `"CONSOLE"`, you can assert that logger output contains expected email content.
  - For `"FILE"`, you can inspect the generated email files.
- **Mocking:** `pytest-mock` can be used to mock `email_service.send_email` or the underlying TES API call (`httpx.AsyncClient.post`) to verify it's called with correct arguments without actual sending.
- **Celery Testing:** Use `task_always_eager=True` to test the email sending logic within Celery tasks synchronously.
- **Dedicated Integration Tests (Occasional):** For testing against a sandbox/dev account of your chosen TES provider, but these should be limited and clearly marked to avoid sending real emails.
