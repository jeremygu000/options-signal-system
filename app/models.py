"""Data models — structured output for every layer."""

from __future__ import annotations

from datetime import date, datetime
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


# ── IV Analysis models ───────────────────────────────────────────────


class IVSkewPointModel(BaseModel):
    strike: float
    implied_volatility: float
    option_type: str
    moneyness: float  # strike / spot


class IVTermPointModel(BaseModel):
    expiration: str
    dte_days: int
    atm_iv: float


class HVPointModel(BaseModel):
    window_days: int
    realized_vol: float  # annualised decimal, e.g. 0.25 = 25%
    label: str


class IVAnalysisResponse(BaseModel):
    symbol: str
    spot_price: float = 0.0
    current_atm_iv: float = 0.0
    iv_rank: float = 0.0
    iv_percentile: float = 0.0
    iv_high_52w: float = 0.0
    iv_low_52w: float = 0.0
    skew_points: list[IVSkewPointModel] = Field(default_factory=list)
    put_call_skew: float = 0.0
    term_structure: list[IVTermPointModel] = Field(default_factory=list)
    hv_points: list[HVPointModel] = Field(default_factory=list)
    iv_rv_spread: float = 0.0
    error: str | None = None


# ── Multi-leg strategy models ────────────────────────────────────────


class OptionLegModel(BaseModel):
    option_type: str = Field(description="'c' for call, 'p' for put")
    action: str = Field(description="'buy' or 'sell'")
    strike: float = Field(gt=0)
    expiration: str
    quantity: int = Field(default=1, ge=1, le=100)
    premium: float = Field(ge=0, description="Per-share mid price")
    iv: float = Field(default=0.30, gt=0, le=5.0)


class MultiLegRequest(BaseModel):
    legs: list[OptionLegModel] = Field(min_length=1, max_length=4)
    spot: float = Field(gt=0)
    dte_days: int = Field(default=30, ge=0, le=730)
    risk_free_rate: float = Field(default=0.05, ge=0, le=0.50)


class PnLPointModel(BaseModel):
    price: float
    pnl: float


class AggregatedGreeksModel(BaseModel):
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0
    vega: float = 0.0
    rho: float = 0.0


class MultiLegResponse(BaseModel):
    net_debit_credit: float = 0.0
    max_profit: float = 0.0
    max_loss: float = 0.0
    breakeven_points: list[float] = Field(default_factory=list)
    greeks: AggregatedGreeksModel = Field(default_factory=AggregatedGreeksModel)
    pnl_curve: list[PnLPointModel] = Field(default_factory=list)
    error: str | None = None


# ── Position management models ───────────────────────────────────────


class PositionCreate(BaseModel):
    symbol: str = Field(min_length=1, max_length=10)
    option_type: str = Field(pattern=r"^(call|put)$")
    strike: float = Field(gt=0)
    expiration: date
    quantity: int = Field(description="Positive=long, negative=short, cannot be 0")
    entry_price: float = Field(ge=0)
    entry_date: datetime | None = None
    entry_commission: float = Field(default=0.0, ge=0)
    strategy_name: str | None = None
    tags: str = ""
    notes: str = ""


class PositionUpdate(BaseModel):
    notes: str | None = None
    tags: str | None = None
    strategy_name: str | None = None
    entry_price: float | None = Field(default=None, ge=0)
    entry_commission: float | None = Field(default=None, ge=0)
    quantity: int | None = None


class PositionClose(BaseModel):
    exit_price: float = Field(ge=0)
    exit_commission: float = Field(default=0.0, ge=0)
    exit_date: datetime | None = None


class PositionResponse(BaseModel):
    id: str
    symbol: str
    option_type: str
    strike: float
    expiration: date
    quantity: int
    entry_price: float
    entry_date: datetime
    entry_commission: float
    exit_price: float | None
    exit_date: datetime | None
    exit_commission: float
    status: str
    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float
    strategy_name: str | None
    tags: str
    notes: str
    created_at: datetime
    updated_at: datetime
    unrealized_pnl: float | None = None
    realized_pnl: float | None = None
    total_cost: float | None = None


class PortfolioSummaryResponse(BaseModel):
    total_positions: int = 0
    open_positions: int = 0
    closed_positions: int = 0
    expired_positions: int = 0
    total_unrealized_pnl: float = 0.0
    total_realized_pnl: float = 0.0
    total_cost: float = 0.0
    greeks: AggregatedGreeksModel = Field(default_factory=AggregatedGreeksModel)


class StrategyGroupResponse(BaseModel):
    strategy_name: str
    position_count: int
    open_count: int
    total_realized_pnl: float
    positions: list[PositionResponse] = Field(default_factory=list)


# ── ML enhancement models ────────────────────────────────────────────


class EnhancedSignal(BaseModel):
    symbol: str
    bias: str
    level: str
    action: str = ""
    rationale: list[str] = Field(default_factory=list)
    price: float = 0.0
    trigger_price: float = 0.0
    option_structure: str = ""
    option_hint: str = ""
    timestamp: datetime = Field(default_factory=now_ny)
    score: int = 0
    ml_confidence: float = 0.0
    ml_regime: str = "neutral"
    regime_probabilities: dict[str, float] = Field(default_factory=dict)
    feature_importance: dict[str, float] = Field(default_factory=dict)
    combined_score: float = 0.0


class MLRegimeResponse(BaseModel):
    regime: str
    probabilities: dict[str, float] = Field(default_factory=dict)
    state: int = 0
    source: str = "rule_based"


class TrainingRequest(BaseModel):
    lookback_days: int = Field(default=365, ge=100, le=1825)


class TrainingStatusResponse(BaseModel):
    last_trained: str | None = None
    regime_metrics: dict[str, object] = Field(default_factory=dict)
    scorer_metrics: dict[str, object] = Field(default_factory=dict)
    symbols_trained: list[str] = Field(default_factory=list)
    error: str | None = None
    regime_model_available: bool = False
    scorer_model_available: bool = False
