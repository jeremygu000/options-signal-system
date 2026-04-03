"""Configuration — 从环境变量读取，支持 .env 文件。"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """All configuration centralised here. Values come from env vars or .env file."""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    # ── Data ──────────────────────────────────────────────────────────
    parquet_dir: Path = Field(
        default_factory=lambda: Path.home() / ".market_data" / "parquet",
        description="Parquet data directory (shared with yahoo-finance-data)",
    )

    # ── Symbols ───────────────────────────────────────────────────────
    symbols: list[str] = Field(
        default=["USO", "XOM", "XLE", "CRM"],
        description="Trading symbols to evaluate",
    )
    market_index: str = "QQQ"
    volatility_index: str = "^VIX"

    # ── Polling ───────────────────────────────────────────────────────
    poll_interval: int = Field(default=600, description="Polling interval in seconds")

    # ── Notifications ────────────────────────────────────────────────
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    wechat_webhook_url: str = ""

    # ── Signal filter ─────────────────────────────────────────────────
    strong_only: bool = Field(
        default=False,
        description="Only send notifications for strong signals",
    )

    # ── Strategy defaults ─────────────────────────────────────────────
    daily_lookback_days: int = Field(default=60, description="Days of daily data to load")
    intraday_period: str = Field(default="5d", description="yfinance intraday period")
    intraday_interval: str = Field(default="15m", description="yfinance intraday interval")

    @property
    def telegram_enabled(self) -> bool:
        return bool(self.telegram_bot_token and self.telegram_chat_id)


# Module-level singleton
settings = Settings()
