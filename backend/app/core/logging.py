"""
Structured JSON logging setup using structlog.
"""
import logging
import sys
import structlog
from app.config import settings


def configure_logging() -> None:
    """Configure structlog with JSON output for production, console for dev."""
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if settings.environment == "production":
        processors = shared_processors + [
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ]
    else:
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, settings.log_level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(sys.stdout),
        cache_logger_on_first_use=True,
    )

    # Suppress noisy third-party loggers
    for name in ("uvicorn.access", "sqlalchemy.engine", "multipart"):
        logging.getLogger(name).setLevel(logging.WARNING)


def get_logger(name: str = __name__) -> structlog.BoundLogger:
    return structlog.get_logger(name)
