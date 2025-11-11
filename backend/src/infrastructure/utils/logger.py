import logging
import json
import sys
from datetime import datetime
from typing import Any, Dict, Optional
import os

class CloudWatchFormatter(logging.Formatter):
    """Custom formatter for CloudWatch logs with structured JSON output"""
    
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add extra fields if present
        if hasattr(record, 'extra_data'):
            log_entry.update(record.extra_data)
            
        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
            
        return json.dumps(log_entry)

class DietGuardLogger:
    """Centralized logger for DietGuard backend"""
    
    def __init__(self, name: str = "dietguard"):
        self.logger = logging.getLogger(name)
        self._setup_logger()
    
    def _setup_logger(self):
        """Setup logger with CloudWatch-compatible formatting"""
        if self.logger.handlers:
            return  # Already configured
            
        # Set log level from environment or default to INFO
        log_level = os.getenv("LOG_LEVEL", "INFO").upper()
        self.logger.setLevel(getattr(logging, log_level, logging.INFO))
        
        # Create console handler
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(CloudWatchFormatter())
        
        self.logger.addHandler(handler)
        self.logger.propagate = False
    
    def _log(self, level: str, message: str, extra_data: Optional[Dict[str, Any]] = None):
        """Internal logging method"""
        record = self.logger.makeRecord(
            name=self.logger.name,
            level=getattr(logging, level.upper()),
            fn="",
            lno=0,
            msg=message,
            args=(),
            exc_info=None
        )
        
        if extra_data:
            record.extra_data = extra_data
            
        self.logger.handle(record)
    
    def info(self, message: str, **kwargs):
        """Log info message"""
        self._log("INFO", message, kwargs)
    
    def error(self, message: str, **kwargs):
        """Log error message"""
        self._log("ERROR", message, kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log warning message"""
        self._log("WARNING", message, kwargs)
    
    def debug(self, message: str, **kwargs):
        """Log debug message"""
        self._log("DEBUG", message, kwargs)

# Global logger instance
logger = DietGuardLogger("dietguard-backend")