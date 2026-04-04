"""Utility helpers — trading hours, timezone."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from app.logging_config import setup_logging as setup_logging  # noqa: F401 — re-export

NY_TZ = ZoneInfo("America/New_York")


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
