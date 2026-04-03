"""Utility helpers — trading hours, timezone, logging setup."""

from __future__ import annotations

import logging
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import structlog

NY_TZ = ZoneInfo("America/New_York")


def setup_logging(level: int = logging.INFO, json_format: bool = False) -> None:
    """Configure root logger with structlog processors.

    Args:
        level: Logging level (default: INFO).
        json_format: If True, output JSON lines (for production). Otherwise human-readable.
    """
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if json_format:
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)


def now_ny() -> datetime:
    """Current time in New York timezone."""
    return datetime.now(tz=NY_TZ)


def is_market_open() -> bool:
    """Check if US stock market is currently in regular trading hours.

    Mon–Fri 09:30–16:00 ET.
    """
    t = now_ny()
    # Weekday: 0=Mon, 6=Sun
    if t.weekday() >= 5:
        return False
    market_open = t.replace(hour=9, minute=30, second=0, microsecond=0)
    market_close = t.replace(hour=16, minute=0, second=0, microsecond=0)
    return market_open <= t <= market_close
