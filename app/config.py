"""Configuration — 从环境变量读取，支持 .env 文件。"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field, SecretStr
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

    # ── Notifications (secrets) ──────────────────────────────────────
    telegram_bot_token: SecretStr = SecretStr("")
    telegram_chat_id: SecretStr = SecretStr("")
    wechat_webhook_url: SecretStr = SecretStr("")

    # ── CORS ─────────────────────────────────────────────────────────
    cors_origins: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:3100", "http://localhost:8300"],
        description="Allowed CORS origins",
    )

    # ── Rate limiting ────────────────────────────────────────────────
    rate_limit_per_minute: int = Field(default=60, description="Max requests per minute per IP")

    # ── Signal filter ─────────────────────────────────────────────────
    strong_only: bool = Field(
        default=False,
        description="Only send notifications for strong signals",
    )

    # ── Strategy defaults ─────────────────────────────────────────────
    daily_lookback_days: int = Field(default=60, description="Days of daily data to load")
    intraday_period: str = Field(default="5d", description="yfinance intraday period")
    intraday_interval: str = Field(default="15m", description="yfinance intraday interval")

    # ── Backtest defaults ────────────────────────────────────────────
    backtest_max_entry_dte: int = Field(default=45, description="Default max DTE for entry")
    backtest_exit_dte: int = Field(default=21, description="Default DTE for exit")
    backtest_capital: float = Field(default=100_000.0, description="Default starting capital")
    backtest_commission: float = Field(default=0.65, description="Commission per contract")

    # ── AI / Ollama ──────────────────────────────────────────────────
    ollama_base_url: str = Field(default="http://localhost:11434", description="Ollama API base URL")
    ollama_model: str = Field(default="qwen3:32b", description="Ollama model name for AI interpretation")

    @property
    def telegram_enabled(self) -> bool:
        return bool(self.telegram_bot_token.get_secret_value() and self.telegram_chat_id.get_secret_value())


# Module-level singleton
settings = Settings()
