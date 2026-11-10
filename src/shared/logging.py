"""Structured logging with correlation ID tracing and automatic secret masking."""

import contextvars
import json
import logging
import re
import sys
from datetime import UTC, datetime
from typing import Any

# Context variable for distributed request / trace tracking
correlation_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar(
    "correlation_id", default="system"
)

# Sensitive patterns that must never appear in logs
SENSITIVE_KEYS = {"authorization", "password", "token", "secret", "api_key", "access_token"}
AUTH_HEADER_REGEX = re.compile(r"(Bearer\s+)[A-Za-z0-9\-._~+/]+=*", re.IGNORECASE)
SECRET_ASSIGN_REGEX = re.compile(
    r"(api[-_]?key|password|secret|token)\s*[:=]\s*['\"]?([A-Za-z0-9\-._~+/]+)['\"]?",
    re.IGNORECASE,
)


def mask_sensitive_str(text: str) -> str:
    """Mask credentials and authorization tokens from raw log strings."""
    text = AUTH_HEADER_REGEX.sub(r"\1[REDACTED]", text)
    text = SECRET_ASSIGN_REGEX.sub(r"\1: [REDACTED]", text)
    return text


def sanitize_payload(payload: Any) -> Any:
    """Recursively scrub sensitive keys from dictionaries and lists."""
    if isinstance(payload, dict):
        scrubbed = {}
        for k, v in payload.items():
            if str(k).lower() in SENSITIVE_KEYS:
                scrubbed[k] = "[REDACTED]"
            else:
                scrubbed[k] = sanitize_payload(v)
        return scrubbed
    elif isinstance(payload, list):
        return [sanitize_payload(item) for item in payload]
    elif isinstance(payload, str):
        return mask_sensitive_str(payload)
    return payload


class JSONFormatter(logging.Formatter):
    """Formats log records as structured single-line JSON."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": mask_sensitive_str(record.getMessage()),
            "correlation_id": correlation_id_ctx.get(),
            "module": record.module,
            "line": record.lineno,
        }

        # Include custom extra fields if passed
        if hasattr(record, "extra_fields") and isinstance(record.extra_fields, dict):
            log_entry["data"] = sanitize_payload(record.extra_fields)

        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, ensure_ascii=False)


def configure_logging(level: str = "INFO", json_format: bool = True) -> None:
    """Configure root and application loggers."""
    root_logger = logging.getLogger()
    root_logger.setLevel(level.upper())

    # Clear existing handlers
    root_logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    if json_format:
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)s] [%(name)s] [%(correlation_id)s]: %(message)s"
            )
        )

    root_logger.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    """Return a logger instance with extra helper capabilities."""
    return logging.getLogger(name)
