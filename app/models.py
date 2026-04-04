"""Data models — structured output for every layer."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from app.utils import now_ny

# ── Enums ────────────────────────────────────────────────────────────


class MarketRegime(str, Enum):
    RISK_ON = "risk_on"
    NEUTRAL = "neutral"
    RISK_OFF = "risk_off"


class SignalLevel(str, Enum):
    STRONG = "强信号"
    WATCH = "观察信号"
    NONE = "无信号"


class Bias(str, Enum):
    SHORT = "逢高做空"
    LONG = "逢低做多"


# ── Market regime result ─────────────────────────────────────────────


class MarketRegimeResult(BaseModel):
    regime: MarketRegime
    reasons: list[str] = Field(default_factory=list)
    qqq_price: float = 0.0
    vix_price: float = 0.0
    timestamp: datetime = Field(default_factory=now_ny)


# ── Strategy config per symbol ───────────────────────────────────────


class StrategyConfig(BaseModel):
    symbol: str
    bias: Bias
    description: str = ""


# ── Signal output ────────────────────────────────────────────────────


class Signal(BaseModel):
    symbol: str
    bias: Bias
    level: SignalLevel
    action: str = ""
    rationale: list[str] = Field(default_factory=list)
    price: float = 0.0
    trigger_price: float = 0.0
    option_structure: str = ""
    option_hint: str = ""
    timestamp: datetime = Field(default_factory=now_ny)
    score: int = Field(default=0, description="Internal score used to determine signal level")


# ── Backtest models ──────────────────────────────────────────────────


class BacktestRequest(BaseModel):
    symbol: str
    strategy: str = Field(default="short_call_spread", description="optopsy strategy name")
    max_entry_dte: int = Field(default=45, ge=7, le=180)
    exit_dte: int = Field(default=21, ge=0, le=90)
    leg1_delta: float = Field(default=0.30, ge=0.05, le=0.95)
    leg2_delta: float = Field(default=0.16, ge=0.05, le=0.95)
    capital: float = Field(default=100_000.0, ge=1_000.0, le=10_000_000.0)
    quantity: int = Field(default=1, ge=1, le=100)
    max_positions: int = Field(default=1, ge=1, le=50)
    commission_per_contract: float = Field(default=0.65, ge=0.0, le=10.0)
    stop_loss: float | None = Field(default=None, ge=0.0, le=1.0)
    take_profit: float | None = Field(default=None, ge=0.0, le=10.0)
    max_expirations: int = Field(default=4, ge=1, le=12)


class BacktestMetrics(BaseModel):
    total_trades: int = 0
    win_rate: float = 0.0
    mean_return: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    max_drawdown: float = 0.0
    profit_factor: float = 0.0
    calmar_ratio: float = 0.0
    final_equity: float = 0.0


class BacktestResponse(BaseModel):
    symbol: str
    strategy: str
    metrics: BacktestMetrics
    equity_curve: list[float] = Field(default_factory=list)
    trade_count: int = 0
    error: str | None = None
    timestamp: datetime = Field(default_factory=now_ny)


class OptionsChainSummary(BaseModel):
    symbol: str
    expirations: list[str] = Field(default_factory=list)
    total_contracts: int = 0
    calls_count: int = 0
    puts_count: int = 0


class OptionsContract(BaseModel):
    """Single option contract with pricing and Greeks."""

    option_type: str = Field(description="'c' for call, 'p' for put")
    expiration: str
    strike: float
    bid: float
    ask: float
    volume: int = 0
    open_interest: int = 0
    implied_volatility: float = 0.0
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0
    vega: float = 0.0
    rho: float = 0.0


class OptionsChainDetail(BaseModel):
    """Full per-contract options chain with Greeks."""

    symbol: str
    expirations: list[str] = Field(default_factory=list)
    total_contracts: int = 0
    calls_count: int = 0
    puts_count: int = 0
    contracts: list[OptionsContract] = Field(default_factory=list)
