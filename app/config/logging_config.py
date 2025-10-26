"""
Structured Logging Configuration
"""
import logging
import sys
import json
from datetime import datetime
from typing import Any, Dict
from app.config.settings import settings

class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging"""
    
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "environment": settings.ENVIRONMENT,
        }
        
        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        # Add extra fields
        if hasattr(record, 'extra_fields'):
            log_entry.update(record.extra_fields)
        
        return json.dumps(log_entry, ensure_ascii=False)

def setup_logging():
    """Setup structured logging configuration"""
    
    # Determine log level based on environment
    if settings.ENVIRONMENT == "production":
        log_level = logging.INFO
    else:
        log_level = logging.DEBUG
    
    # Create root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    
    # Set formatter based on environment
    if settings.ENVIRONMENT == "production":
        # Use JSON formatter for production
        console_handler.setFormatter(JSONFormatter())
    else:
        # Use simple formatter for development
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(formatter)
    
    root_logger.addHandler(console_handler)
    
    # Add file handler for production
    if settings.ENVIRONMENT == "production":
        try:
            # Create logs directory if it doesn't exist
            import os
            os.makedirs("logs", exist_ok=True)
            
            # File handler for application logs
            file_handler = logging.FileHandler("logs/app.log")
            file_handler.setLevel(logging.INFO)
            file_handler.setFormatter(JSONFormatter())
            root_logger.addHandler(file_handler)
            
            # File handler for error logs
            error_handler = logging.FileHandler("logs/error.log")
            error_handler.setLevel(logging.ERROR)
            error_handler.setFormatter(JSONFormatter())
            root_logger.addHandler(error_handler)
            
        except Exception as e:
            # If we can't create log files, continue without them
            logging.warning(f"Could not create log files: {e}")
    
    # Set specific loggers
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("fastapi").setLevel(logging.INFO)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    
    # Log startup message
    logger = logging.getLogger(__name__)
    logger.info("Logging system initialized", extra={
        "extra_fields": {
            "environment": settings.ENVIRONMENT,
            "log_level": log_level,
            "debug_mode": settings.DEBUG
        }
    })

def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the given name"""
    return logging.getLogger(name)

def log_request(logger: logging.Logger, request_data: Dict[str, Any]):
    """Log HTTP request data"""
    logger.info("HTTP Request", extra={
        "extra_fields": {
            "method": request_data.get("method"),
            "url": request_data.get("url"),
            "user_agent": request_data.get("user_agent"),
            "client_ip": request_data.get("client_ip"),
            "user_id": request_data.get("user_id"),
            "company_id": request_data.get("company_id")
        }
    })

def log_error(logger: logging.Logger, error: Exception, context: Dict[str, Any] = None):
    """Log error with context"""
    logger.error(f"Error occurred: {str(error)}", exc_info=True, extra={
        "extra_fields": {
            "error_type": type(error).__name__,
            "context": context or {}
        }
    })

