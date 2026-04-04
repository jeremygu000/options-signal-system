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


# ── Symbol discovery ─────────────────────────────────────────────────


class SymbolMetaResponse(BaseModel):
    symbol: str
    rows: int
    first_date: str
    last_date: str
    avg_volume: float
    last_close: float
    return_1y: float


class PaginatedSymbolResult(BaseModel):
    items: list[SymbolMetaResponse]
    total: int
    offset: int
    limit: int


# ── Signal backtest models ───────────────────────────────────────────


class SignalBacktestRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=10)
    start_date: date | None = Field(default=None, description="Backtest start (default: 1 year ago)")
    end_date: date | None = Field(default=None, description="Backtest end (default: today)")
    horizons: list[int] = Field(default=[1, 3, 5, 10, 20], description="Forward-return horizons in days")


class SignalOutcome(BaseModel):
    date: date
    signal_level: str
    bias: str
    score: int
    price: float
    returns: dict[str, float] = Field(
        default_factory=dict, description="Horizon → forward return, e.g. {'1d': 0.012, '5d': -0.003}"
    )
    hit: dict[str, bool] = Field(default_factory=dict, description="Horizon → whether direction was correct")


class HorizonBreakdown(BaseModel):
    horizon: str
    total_signals: int = 0
    hits: int = 0
    hit_rate: float = 0.0
    avg_return: float = 0.0
    strong_signals: int = 0
    strong_hits: int = 0
    strong_hit_rate: float = 0.0
    watch_signals: int = 0
    watch_hits: int = 0
    watch_hit_rate: float = 0.0


class RegimeBreakdown(BaseModel):
    regime: str
    total_signals: int = 0
    hit_rate: float = 0.0
    avg_return: float = 0.0


class SignalBacktestMetrics(BaseModel):
    total_days: int = 0
    signal_days: int = 0
    strong_days: int = 0
    watch_days: int = 0
    none_days: int = 0
    overall_hit_rate: float = 0.0
    avg_return: float = 0.0
    profit_factor: float = 0.0
    max_drawdown: float = 0.0
    sharpe: float = 0.0
    by_horizon: list[HorizonBreakdown] = Field(default_factory=list)
    by_regime: list[RegimeBreakdown] = Field(default_factory=list)


class SignalBacktestResponse(BaseModel):
    symbol: str
    start_date: date
    end_date: date
    metrics: SignalBacktestMetrics = Field(default_factory=SignalBacktestMetrics)
    outcomes: list[SignalOutcome] = Field(default_factory=list)
    equity_curve: list[float] = Field(default_factory=list)
    error: str | None = None
    timestamp: datetime = Field(default_factory=now_ny)


class WalkForwardWindow(BaseModel):
    train_start: date
    train_end: date
    test_start: date
    test_end: date
    in_sample_hit_rate: float = 0.0
    out_of_sample_hit_rate: float = 0.0
    out_of_sample_return: float = 0.0


class WalkForwardRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=10)
    train_days: int = Field(default=252, ge=60, le=756)
    test_days: int = Field(default=63, ge=21, le=252)
    step_days: int = Field(default=21, ge=5, le=63)
    horizon: int = Field(default=5, ge=1, le=20)


class WalkForwardResponse(BaseModel):
    symbol: str
    windows: list[WalkForwardWindow] = Field(default_factory=list)
    avg_oos_hit_rate: float = 0.0
    avg_oos_return: float = 0.0
    stability_ratio: float = Field(default=0.0, description="OOS hit rate / IS hit rate — closer to 1.0 is better")
    error: str | None = None
    timestamp: datetime = Field(default_factory=now_ny)


# ── Broker / trading models ──────────────────────────────────────────


class OrderSideEnum(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderTypeEnum(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class TimeInForceEnum(str, Enum):
    DAY = "day"
    GTC = "gtc"
    IOC = "ioc"
    FOK = "fok"


class OrderStatusEnum(str, Enum):
    NEW = "new"
    ACCEPTED = "accepted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    DONE_FOR_DAY = "done_for_day"
    CANCELED = "canceled"
    EXPIRED = "expired"
    REPLACED = "replaced"
    REJECTED = "rejected"
    PENDING_NEW = "pending_new"
    PENDING_CANCEL = "pending_cancel"
    PENDING_REPLACE = "pending_replace"


class CreateOrderRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=10)
    side: OrderSideEnum
    order_type: OrderTypeEnum = OrderTypeEnum.MARKET
    time_in_force: TimeInForceEnum = TimeInForceEnum.DAY
    qty: float | None = Field(default=None, gt=0, description="Number of shares (mutually exclusive with notional)")
    notional: float | None = Field(default=None, gt=0, description="Dollar amount (mutually exclusive with qty)")
    limit_price: float | None = Field(default=None, gt=0)
    stop_price: float | None = Field(default=None, gt=0)


class OrderResponse(BaseModel):
    id: str
    symbol: str
    side: str
    order_type: str
    time_in_force: str
    qty: str | None = None
    notional: str | None = None
    limit_price: str | None = None
    stop_price: str | None = None
    filled_qty: str | None = None
    filled_avg_price: str | None = None
    status: str
    created_at: str | None = None
    updated_at: str | None = None
    submitted_at: str | None = None
    filled_at: str | None = None
    expired_at: str | None = None
    canceled_at: str | None = None


class AccountInfoResponse(BaseModel):
    id: str
    status: str
    cash: float
    equity: float
    portfolio_value: float
    buying_power: float
    long_market_value: float
    short_market_value: float
    pattern_day_trader: bool
    trading_blocked: bool
    transfers_blocked: bool
    currency: str = "USD"


class BrokerPositionResponse(BaseModel):
    symbol: str
    qty: str
    side: str
    market_value: str | None = None
    avg_entry_price: str | None = None
    current_price: str | None = None
    unrealized_pl: str | None = None
    unrealized_plpc: str | None = None
    cost_basis: str | None = None
    change_today: str | None = None


class ClosePositionRequest(BaseModel):
    qty: float | None = Field(default=None, gt=0, description="Shares to close (default: close all)")
    percentage: float | None = Field(default=None, gt=0, le=100, description="Percentage to close (default: close all)")


class PortfolioHistoryRequest(BaseModel):
    period: str = Field(default="1M", pattern=r"^(1D|1W|1M|3M|6M|1A|2A|all)$")
    timeframe: str = Field(default="1D", pattern=r"^(1Min|5Min|15Min|1H|1D)$")
    extended_hours: bool = False


class PortfolioHistoryResponse(BaseModel):
    timestamp: list[int] = Field(default_factory=list)
    equity: list[float] = Field(default_factory=list)
    profit_loss: list[float] = Field(default_factory=list)
    profit_loss_pct: list[float] = Field(default_factory=list)
    base_value: float = 0.0


# ── Fundamental analysis models ──────────────────────────────────────


class ValuationMetricsModel(BaseModel):
    market_cap: float = 0.0
    trailing_pe: float = 0.0
    forward_pe: float = 0.0
    trailing_eps: float = 0.0
    forward_eps: float = 0.0
    price_to_book: float = 0.0
    price_to_sales: float = 0.0
    peg_ratio: float = 0.0
    enterprise_value: float = 0.0
    ev_to_ebitda: float = 0.0
    dividend_yield: float = 0.0  # decimal, e.g. 0.02 = 2%
    beta: float = 0.0


class AnalystRatingModel(BaseModel):
    recommendation_key: str = ""
    recommendation_mean: float = 0.0  # 1.0 = strong buy, 5.0 = strong sell
    strong_buy: int = 0
    buy: int = 0
    hold: int = 0
    sell: int = 0
    strong_sell: int = 0
    number_of_analysts: int = 0


class PriceTargetModel(BaseModel):
    current: float = 0.0
    low: float = 0.0
    high: float = 0.0
    mean: float = 0.0
    median: float = 0.0
    number_of_analysts: int = 0


class EarningsSurpriseModel(BaseModel):
    date: str
    eps_estimate: float = 0.0
    eps_actual: float = 0.0
    surprise_pct: float = 0.0


class UpgradeDowngradeModel(BaseModel):
    date: str
    firm: str
    to_grade: str
    from_grade: str
    action: str


class ShortInterestModel(BaseModel):
    short_ratio: float = 0.0  # days to cover
    short_pct_of_float: float = 0.0  # decimal, e.g. 0.05 = 5%
    shares_short: int = 0


class IncomeHighlightsModel(BaseModel):
    revenue: float = 0.0
    revenue_growth: float = 0.0
    gross_margin: float = 0.0
    operating_margin: float = 0.0
    profit_margin: float = 0.0
    earnings_growth: float = 0.0


class FundamentalAnalysisResponse(BaseModel):
    symbol: str
    spot_price: float = 0.0
    currency: str = "USD"
    valuation: ValuationMetricsModel = Field(default_factory=ValuationMetricsModel)
    analyst_rating: AnalystRatingModel = Field(default_factory=AnalystRatingModel)
    price_target: PriceTargetModel = Field(default_factory=PriceTargetModel)
    short_interest: ShortInterestModel = Field(default_factory=ShortInterestModel)
    income: IncomeHighlightsModel = Field(default_factory=IncomeHighlightsModel)
    earnings_surprises: list[EarningsSurpriseModel] = Field(default_factory=list)
    upgrades_downgrades: list[UpgradeDowngradeModel] = Field(default_factory=list)
    next_earnings_date: str | None = None
    error: str | None = None


# ── Put/Call ratio models ────────────────────────────────────────────


class PCRStrikePointModel(BaseModel):
    strike: float
    call_volume: int = 0
    put_volume: int = 0
    call_oi: int = 0
    put_oi: int = 0
    pcr_volume: float = 0.0
    pcr_oi: float = 0.0
    moneyness: float = 0.0


class PCRTermPointModel(BaseModel):
    expiration: str
    dte_days: int
    call_volume: int = 0
    put_volume: int = 0
    call_oi: int = 0
    put_oi: int = 0
    pcr_volume: float = 0.0
    pcr_oi: float = 0.0


class PutCallRatioResponse(BaseModel):
    symbol: str
    spot_price: float = 0.0
    total_call_volume: int = 0
    total_put_volume: int = 0
    total_call_oi: int = 0
    total_put_oi: int = 0
    pcr_volume: float = 0.0
    pcr_oi: float = 0.0
    atm_pcr_volume: float = 0.0
    atm_pcr_oi: float = 0.0
    signal: str = "neutral"
    signal_description: str = ""
    strike_points: list[PCRStrikePointModel] = Field(default_factory=list)
    term_structure: list[PCRTermPointModel] = Field(default_factory=list)
    expirations_analysed: int = 0
    error: str | None = None


# ── Unusual options volume models ────────────────────────────────────


class UnusualStrikeModel(BaseModel):
    expiration: str
    dte_days: int
    strike: float
    option_type: str
    volume: int
    open_interest: int
    voi_ratio: float
    bid: float
    ask: float
    mid_price: float
    implied_volatility: float
    premium: float
    moneyness: float
    size_category: str


class ClusterSummaryModel(BaseModel):
    is_clustered: bool = False
    pattern: str = "none"
    unusual_call_count: int = 0
    unusual_put_count: int = 0
    total_premium: float = 0.0
    total_contracts: int = 0


class UnusualVolumeResponse(BaseModel):
    symbol: str
    spot_price: float = 0.0
    total_contracts_scanned: int = 0
    unusual_strikes_found: int = 0
    total_unusual_premium: float = 0.0
    signal: str = "neutral"
    signal_description: str = ""
    score: int = 0
    strikes: list[UnusualStrikeModel] = Field(default_factory=list)
    cluster: ClusterSummaryModel | None = None
    expirations_scanned: int = 0
    error: str | None = None
