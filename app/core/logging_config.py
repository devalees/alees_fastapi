import logging
import sys
import time
from typing import Dict, Any, Optional

from pythonjsonlogger import jsonlogger

from app.core.config import settings
from app.core.request_context import get_request_id

class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """
    Custom JSON formatter for logging that adds standard fields and request context.
    """
    
    def add_fields(self, log_record: Dict[str, Any], record: logging.LogRecord, message_dict: Dict[str, Any]) -> None:
        super().add_fields(log_record, record, message_dict)
        
        # Add timestamps
        log_record["timestamp"] = time.strftime(
            "%Y-%m-%dT%H:%M:%S.%fZ", time.gmtime()
        )
        
        # Add log level
        log_record["level"] = record.levelname
        log_record["name"] = record.name

        # Add app name and environment
        log_record["app"] = settings.APP_NAME
        log_record["environment"] = settings.ENVIRONMENT
        
        # Add request_id from context if available
        request_id = get_request_id()
        if request_id:
            log_record["request_id"] = request_id
        
        # Add exception info if present
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)


def setup_logging(log_level: Optional[str] = None) -> None:
    """
    Set up structured JSON logging.
    
    Args:
        log_level: Optional override for the log level set in settings.
    """
    if log_level is None:
        log_level = settings.LOG_LEVEL
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Clear existing handlers to prevent duplication
    if root_logger.handlers:
        for handler in root_logger.handlers:
            root_logger.removeHandler(handler)
    
    # Create and configure handler to output to stdout
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(log_level)
    
    # Use our custom JSON formatter
    formatter = CustomJsonFormatter(
        "%(message)s %(levelname)s %(name)s %(module)s %(funcName)s %(lineno)d",
    )
    handler.setFormatter(formatter)
    
    # Add handler to root logger
    root_logger.addHandler(handler)
    
    # Configure library loggers
    logging.getLogger("uvicorn").setLevel(log_level)
    logging.getLogger("uvicorn.access").setLevel(log_level)
    
    # Set conservative log levels for noisy libraries
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)
    
    # Log initial message
    logging.info(
        f"Logging configured with level {log_level} for {settings.APP_NAME} in {settings.ENVIRONMENT} environment"
    ) 