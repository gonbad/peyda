"""
Structured logging configuration.
Outputs JSON logs for production, human-readable for development.
"""
import logging
import json
import sys
from typing import Any, Dict


class StructuredFormatter(logging.Formatter):
    """JSON formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data: Dict[str, Any] = {
            'timestamp': self.formatTime(record),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
        }
        
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
        
        if hasattr(record, 'user_id'):
            log_data['user_id'] = record.user_id
        
        if hasattr(record, 'request_id'):
            log_data['request_id'] = record.request_id
        
        for key, value in record.__dict__.items():
            if key not in (
                'name', 'msg', 'args', 'created', 'filename', 'funcName',
                'levelname', 'levelno', 'lineno', 'module', 'msecs',
                'pathname', 'process', 'processName', 'relativeCreated',
                'stack_info', 'exc_info', 'exc_text', 'thread', 'threadName',
                'message', 'user_id', 'request_id'
            ) and not key.startswith('_'):
                log_data[key] = value
        
        return json.dumps(log_data, ensure_ascii=False, default=str)


class DevelopmentFormatter(logging.Formatter):
    """Human-readable formatter for development."""
    
    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
    }
    RESET = '\033[0m'
    
    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, '')
        
        parts = [
            f"{color}{record.levelname:8}{self.RESET}",
            f"[{record.name}]",
            record.getMessage()
        ]
        
        extra_fields = []
        for key, value in record.__dict__.items():
            if key not in (
                'name', 'msg', 'args', 'created', 'filename', 'funcName',
                'levelname', 'levelno', 'lineno', 'module', 'msecs',
                'pathname', 'process', 'processName', 'relativeCreated',
                'stack_info', 'exc_info', 'exc_text', 'thread', 'threadName',
                'message'
            ) and not key.startswith('_'):
                extra_fields.append(f"{key}={value}")
        
        if extra_fields:
            parts.append(f"({', '.join(extra_fields)})")
        
        return ' '.join(parts)


def configure_logging(is_production: bool = False, level: str = 'INFO'):
    """
    Configure logging for the application.
    
    Args:
        is_production: Use JSON formatter if True, otherwise colored output
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))
    
    root_logger.handlers.clear()
    
    handler = logging.StreamHandler(sys.stdout)
    
    if is_production:
        handler.setFormatter(StructuredFormatter())
    else:
        handler.setFormatter(DevelopmentFormatter())
    
    root_logger.addHandler(handler)
    
    logging.getLogger('pika').setLevel(logging.WARNING)
    logging.getLogger('redis').setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the given name."""
    return logging.getLogger(name)
