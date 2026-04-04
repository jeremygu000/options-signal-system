"""FastAPI server — REST API for the web dashboard.

Start:
    uvicorn app.server:app --port 8400 --reload
"""

from __future__ import annotations

import asyncio
import json as _json
import logging
import time
import uuid
from contextlib import asynccontextmanager
from functools import lru_cache
from typing import Annotated, Any, AsyncIterator

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import httpx
import pandas as pd
from pydantic import BaseModel, Field

from app.backtester import BacktestConfig, StrategyType, run_backtest, run_multi_strategy_backtest
from app.config import settings
from app.security import ApiKey, check_rate_limit_ip
from app.data_provider import (
    clear_cache as clear_data_cache,
    get_available_symbols,
    get_daily,
    get_intraday,
    has_parquet_data,
)
from app.database import close_db, get_session, init_db
from app.fundamental import FundamentalAnalysisResult, compute_fundamental_analysis
from app.put_call_ratio import PutCallRatioResult, compute_put_call_ratio
from app.unusual_volume import UnusualVolumeResult, compute_unusual_volume
from app.greeks import GreeksResult, calculate_greeks
from app.iv_analysis import IVAnalysisResult, compute_iv_analysis
from app.multi_leg import OptionLeg, analyze_multi_leg
from app.indicators import atr, prev_day_high, prev_day_low, rolling_high, rolling_low, session_vwap, sma
from app.market_regime import MarketRegimeEngine
from app.models import (
    AggregatedGreeksModel,
    AnalystRatingModel,
    BacktestMetrics,
    BacktestRequest,
    BacktestResponse,
    EarningsSurpriseModel,
    EnhancedSignal,
    FundamentalAnalysisResponse,
    HVPointModel,
    IncomeHighlightsModel,
    IVAnalysisResponse,
    IVSkewPointModel,
    IVTermPointModel,
    MarketRegimeResult,
    MLRegimeResponse,
    MultiLegRequest,
    MultiLegResponse,
    OptionsChainDetail,
    OptionsChainSummary,
    OptionsContract,
    PnLPointModel,
    PortfolioSummaryResponse,
    PositionClose,
    PositionCreate,
    PositionResponse,
    PositionUpdate,
    PriceTargetModel,
    Signal,
    SignalLevel,
    ShortInterestModel,
    StrategyGroupResponse,
    TrainingRequest,
    TrainingStatusResponse,
    UpgradeDowngradeModel,
    ValuationMetricsModel,
    SymbolMetaResponse,
    PaginatedSymbolResult,
    PCRStrikePointModel,
    PCRTermPointModel,
    SignalBacktestRequest,
    SignalBacktestResponse,
    WalkForwardRequest,
    WalkForwardResponse,
    CreateOrderRequest,
    OrderResponse,
    AccountInfoResponse,
    BrokerPositionResponse,
    ClosePositionRequest as BrokerClosePositionRequest,
    PortfolioHistoryRequest,
    PortfolioHistoryResponse,
    PutCallRatioResponse,
    UnusualStrikeModel,
    ClusterSummaryModel,
    UnusualVolumeResponse,
)
from app.options_data import clear_chain_cache, get_expirations, get_options_chain, get_options_chain_multi
from app.options_source import get_options_source
from app.position_models import Position
from app.positions import (
    aggregate_greeks,
    calc_realized_pnl,
    calc_total_cost,
    calc_unrealized_pnl,
    close_position,
    create_position,
    delete_position,
    get_expiring_positions,
    get_position,
    group_by_strategy,
    list_positions,
    mark_expired_positions,
    update_position,
)
from app.signal_backtest import run_signal_backtest, run_walk_forward
from app.broker import AlpacaBroker, get_broker
from app.strategy_engine import StrategyEngine
from app.symbol_discovery import build_metadata_index, clear_discovery_cache, search_symbols
from app.ws import broadcaster, handle_client_message, manager as ws_manager
from app.ml.llm_analyzer import stream_signal_analysis
from app.ml.pipeline import TrainingStatus, load_status, run_training_pipeline
from app.ml.regime_classifier import RegimeClassifier
from app.ml.signal_scorer import SignalScorer
from app.utils import now_ny

logger = logging.getLogger(__name__)

CORE_SYMBOLS: set[str] = {s.upper() for s in [settings.market_index, settings.volatility_index, *settings.symbols]}


# ── Response models ──────────────────────────────────────────────────


class HealthResponse(BaseModel):
    status: str
    timestamp: str
    data_status: dict[str, bool] = Field(default_factory=dict)
    version: str = "0.1.0"


class SymbolInfo(BaseModel):
    symbol: str
    has_daily: bool
    daily_rows: int
    last_date: str


class IndicatorSnapshot(BaseModel):
    symbol: str
    price: float
    sma5: float | None
    sma10: float | None
    atr14: float | None
    vwap: float | None
    prev_high: float | None
    prev_low: float | None
    rolling_high_20: float | None
    rolling_low_20: float | None
    range_position: float | None


class FullScanResponse(BaseModel):
    regime: MarketRegimeResult
    signals: list[Signal]
    timestamp: str


class OHLCVBar(BaseModel):
    date: str
    time: int
    open: float
    high: float
    low: float
    close: float
    volume: float


class CompareBar(BaseModel):
    date: str
    time: int
    close: float


class PaginatedOHLCV(BaseModel):
    data: list[OHLCVBar]
    total: int
    offset: int
    limit: int


class ErrorResponse(BaseModel):
    detail: str
    request_id: str


class GreeksRequest(BaseModel):
    spot: float = Field(gt=0, description="Underlying price")
    strike: float = Field(gt=0, description="Strike price")
    dte_days: int = Field(ge=0, le=3650, description="Days to expiration")
    risk_free_rate: float = Field(default=0.05, ge=0.0, le=1.0)
    iv: float = Field(gt=0, le=5.0, description="Implied volatility (decimal, e.g. 0.30)")
    option_type: str = Field(pattern=r"^[cp]$", description="'c' for call, 'p' for put")


class GreeksResponse(BaseModel):
    price: float
    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float


# ── Dependencies (DI) ───────────────────────────────────────────────


@lru_cache(maxsize=1)
def get_regime_engine() -> MarketRegimeEngine:
    return MarketRegimeEngine(
        qqq_symbol=settings.market_index,
        vix_symbol=settings.volatility_index,
    )


@lru_cache(maxsize=1)
def get_strategy_engine() -> StrategyEngine:
    return StrategyEngine()


@lru_cache(maxsize=1)
def get_regime_classifier() -> RegimeClassifier:
    clf = RegimeClassifier()
    clf.load()  # silently no-op if no saved model
    return clf


@lru_cache(maxsize=1)
def get_signal_scorer() -> SignalScorer:
    scorer = SignalScorer()
    scorer.load()  # silently no-op if no saved model
    return scorer


def validate_symbol(symbol: str) -> str:
    upper = symbol.upper()
    if upper not in CORE_SYMBOLS and not has_parquet_data(upper):
        raise HTTPException(status_code=400, detail=f"Unknown symbol: {symbol}. No Parquet data found.")
    return upper


def validate_days(days: int = Query(default=90, ge=1, le=365)) -> int:
    return days


ValidSymbol = Annotated[str, Depends(validate_symbol)]
ValidDays = Annotated[int, Depends(validate_days)]
RegimeEngine = Annotated[MarketRegimeEngine, Depends(get_regime_engine)]
StratEngine = Annotated[StrategyEngine, Depends(get_strategy_engine)]
MLRegime = Annotated[RegimeClassifier, Depends(get_regime_classifier)]
MLScorer = Annotated[SignalScorer, Depends(get_signal_scorer)]


# ── App ──────────────────────────────────────────────────────────────


# -- WebSocket data providers (called by Broadcaster) --


async def _ws_signals_provider() -> dict[str, Any] | None:
    loop = asyncio.get_event_loop()
    engine = get_regime_engine()
    strat = get_strategy_engine()
    regime = await loop.run_in_executor(None, engine.evaluate)

    async def _eval(sym: str) -> dict[str, Any]:
        sig = await loop.run_in_executor(None, strat.evaluate_symbol, sym, regime)
        return sig.model_dump()

    signals = await asyncio.gather(*(_eval(s) for s in settings.symbols))
    return {
        "regime": regime.model_dump(),
        "signals": list(signals),
        "timestamp": now_ny().isoformat(),
    }


async def _ws_regime_provider() -> dict[str, Any] | None:
    loop = asyncio.get_event_loop()
    regime = await loop.run_in_executor(None, get_regime_engine().evaluate)
    return regime.model_dump()


async def _ws_broker_provider() -> dict[str, Any] | None:
    try:
        broker = get_broker()
    except Exception:
        return None
    loop = asyncio.get_event_loop()
    account = await loop.run_in_executor(None, broker.get_account)
    positions = await loop.run_in_executor(None, broker.get_positions)
    orders = await loop.run_in_executor(None, broker.get_orders, "open", 20, None)
    return {
        "account": account.model_dump(),
        "positions": [p.model_dump() for p in positions],
        "orders": [o.model_dump() for o in orders],
    }


async def _ws_health_provider() -> dict[str, Any]:
    return {
        "status": "ok",
        "timestamp": now_ny().isoformat(),
        "ws_clients": ws_manager.client_count,
    }


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
    await init_db()
    broadcaster.register("signals", _ws_signals_provider)
    broadcaster.register("regime", _ws_regime_provider)
    broadcaster.register("broker", _ws_broker_provider)
    broadcaster.register("health", _ws_health_provider)
    await broadcaster.start()
    logger.info("Signal system API started on port 8400")
    yield
    await broadcaster.stop()
    get_regime_engine.cache_clear()
    get_strategy_engine.cache_clear()
    get_regime_classifier.cache_clear()
    get_signal_scorer.cache_clear()
    clear_data_cache()
    clear_chain_cache()
    clear_discovery_cache()
    await close_db()
    logger.info("Signal system API shutting down")


tags_metadata = [
    {"name": "health", "description": "Health & status checks"},
    {"name": "market", "description": "Market regime & signal endpoints"},
    {"name": "data", "description": "OHLCV & indicator data"},
    {"name": "options", "description": "Options chain & backtesting"},
    {"name": "signal-backtest", "description": "Signal replay backtesting & walk-forward analysis"},
    {"name": "positions", "description": "Position management & portfolio"},
    {"name": "ml", "description": "ML-enhanced signals, regime & training"},
    {"name": "discovery", "description": "Symbol discovery & metadata"},
    {"name": "broker", "description": "Alpaca broker integration — account, orders, positions, portfolio"},
    {"name": "websocket", "description": "Real-time push via WebSocket"},
]

app = FastAPI(
    title="Options Signal System API",
    version="0.1.0",
    lifespan=lifespan,
    openapi_tags=tags_metadata,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_middleware(request: Request, call_next: object) -> Response:
    request_id = str(uuid.uuid4())[:8]
    request.state.request_id = request_id

    try:
        check_rate_limit_ip(request)
    except HTTPException as exc:
        return Response(content=exc.detail, status_code=exc.status_code, headers={"X-Request-ID": request_id})

    start = time.monotonic()
    try:
        response: Response = await call_next(request)  # type: ignore[operator]
    except Exception:
        logger.exception("Unhandled error [%s] %s %s", request_id, request.method, request.url.path)
        return Response(content="Internal server error", status_code=500, headers={"X-Request-ID": request_id})

    elapsed = time.monotonic() - start
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Response-Time"] = f"{elapsed:.3f}s"
    logger.info("[%s] %s %s → %d (%.3fs)", request_id, request.method, request.url.path, response.status_code, elapsed)
    return response


# ── Endpoints ────────────────────────────────────────────────────────


@app.get("/api/v1/health", response_model=HealthResponse, tags=["health"])
@app.get("/api/health", response_model=HealthResponse, include_in_schema=False)
async def health() -> HealthResponse:
    loop = asyncio.get_event_loop()
    all_symbols = [settings.market_index, settings.volatility_index, *settings.symbols]

    async def check_symbol(sym: str) -> tuple[str, bool]:
        df = await loop.run_in_executor(None, get_daily, sym, None)
        return sym, not df.empty

    results = await asyncio.gather(*(check_symbol(s) for s in all_symbols))
    data_status = dict(results)

    return HealthResponse(
        status="ok",
        timestamp=now_ny().isoformat(),
        data_status=data_status,
    )


@app.get("/api/v1/symbols", response_model=list[SymbolInfo], tags=["data"])
@app.get("/api/symbols", response_model=list[SymbolInfo], include_in_schema=False)
async def list_symbols() -> list[SymbolInfo]:
    loop = asyncio.get_event_loop()
    all_symbols = [settings.market_index, settings.volatility_index, *settings.symbols]

    async def fetch_info(sym: str) -> SymbolInfo:
        df = await loop.run_in_executor(None, get_daily, sym, None)
        last_date = str(df.index[-1].date()) if not df.empty else ""
        return SymbolInfo(symbol=sym, has_daily=not df.empty, daily_rows=len(df), last_date=last_date)

    results = await asyncio.gather(*(fetch_info(s) for s in all_symbols))
    return list(results)


@app.get("/api/v1/regime", response_model=MarketRegimeResult, tags=["market"])
@app.get("/api/regime", response_model=MarketRegimeResult, include_in_schema=False)
async def get_regime(engine: RegimeEngine) -> MarketRegimeResult:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, engine.evaluate)


@app.get("/api/v1/signals", response_model=list[Signal], tags=["market"])
@app.get("/api/signals", response_model=list[Signal], include_in_schema=False)
async def get_signals(regime_engine: RegimeEngine, strategy_engine: StratEngine) -> list[Signal]:
    loop = asyncio.get_event_loop()
    regime = await loop.run_in_executor(None, regime_engine.evaluate)

    async def eval_sym(sym: str) -> Signal:
        return await loop.run_in_executor(None, strategy_engine.evaluate_symbol, sym, regime)

    results = await asyncio.gather(*(eval_sym(s) for s in settings.symbols))
    return list(results)


@app.get("/api/v1/scan", response_model=FullScanResponse, tags=["market"])
@app.get("/api/scan", response_model=FullScanResponse, include_in_schema=False)
async def full_scan(regime_engine: RegimeEngine, strategy_engine: StratEngine) -> FullScanResponse:
    loop = asyncio.get_event_loop()
    regime = await loop.run_in_executor(None, regime_engine.evaluate)

    async def eval_sym(sym: str) -> Signal:
        return await loop.run_in_executor(None, strategy_engine.evaluate_symbol, sym, regime)

    signals = await asyncio.gather(*(eval_sym(s) for s in settings.symbols))
    return FullScanResponse(
        regime=regime,
        signals=list(signals),
        timestamp=now_ny().isoformat(),
    )


@app.get("/api/v1/indicators/{symbol}", response_model=IndicatorSnapshot, tags=["data"])
@app.get("/api/indicators/{symbol}", response_model=IndicatorSnapshot, include_in_schema=False)
async def get_indicators(symbol: ValidSymbol) -> IndicatorSnapshot:
    import math

    loop = asyncio.get_event_loop()
    daily, intraday_df = await asyncio.gather(
        loop.run_in_executor(None, get_daily, symbol, 60),
        loop.run_in_executor(None, get_intraday, symbol),
    )

    if daily.empty:
        return IndicatorSnapshot(
            symbol=symbol,
            price=0.0,
            sma5=None,
            sma10=None,
            atr14=None,
            vwap=None,
            prev_high=None,
            prev_low=None,
            rolling_high_20=None,
            rolling_low_20=None,
            range_position=None,
        )

    close = daily["Close"]
    price = float(close.iloc[-1])

    sma5 = sma(close, 5)
    sma10 = sma(close, 10)
    atr14 = atr(daily, 14)
    rh = rolling_high(daily, 20)
    rl = rolling_low(daily, 20)
    pdh = prev_day_high(daily)
    pdl = prev_day_low(daily)

    sma5_val = float(sma5.iloc[-1]) if not sma5.empty and not math.isnan(float(sma5.iloc[-1])) else None
    sma10_val = float(sma10.iloc[-1]) if not sma10.empty and not math.isnan(float(sma10.iloc[-1])) else None
    atr14_val = float(atr14.iloc[-1]) if not atr14.empty and not math.isnan(float(atr14.iloc[-1])) else None
    rh_val = float(rh.iloc[-1]) if not rh.empty and not math.isnan(float(rh.iloc[-1])) else None
    rl_val = float(rl.iloc[-1]) if not rl.empty and not math.isnan(float(rl.iloc[-1])) else None
    pdh_val = pdh if not math.isnan(pdh) else None
    pdl_val = pdl if not math.isnan(pdl) else None

    vwap_val: float | None = None
    if not intraday_df.empty:
        vwap_series = session_vwap(intraday_df)
        if not vwap_series.empty:
            v = float(vwap_series.iloc[-1])
            if not math.isnan(v):
                vwap_val = v

    range_position: float | None = None
    if rh_val is not None and rl_val is not None and rh_val > rl_val:
        range_position = (price - rl_val) / (rh_val - rl_val)

    return IndicatorSnapshot(
        symbol=symbol,
        price=price,
        sma5=sma5_val,
        sma10=sma10_val,
        atr14=atr14_val,
        vwap=vwap_val,
        prev_high=pdh_val,
        prev_low=pdl_val,
        rolling_high_20=rh_val,
        rolling_low_20=rl_val,
        range_position=range_position,
    )


@app.get("/api/v1/ohlcv/{symbol}", response_model=PaginatedOHLCV, tags=["data"])
@app.get("/api/ohlcv/{symbol}", response_model=PaginatedOHLCV, include_in_schema=False)
async def get_ohlcv(
    symbol: ValidSymbol,
    days: ValidDays,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=500, ge=1, le=1000),
) -> PaginatedOHLCV:
    loop = asyncio.get_event_loop()
    df = await loop.run_in_executor(None, get_daily, symbol, days)
    if df.empty:
        return PaginatedOHLCV(data=[], total=0, offset=offset, limit=limit)

    total = len(df)
    df_page = df.iloc[offset : offset + limit]
    timestamps = pd.DatetimeIndex(df_page.index)

    bars = [
        OHLCVBar(
            date=str(timestamps[i].date()),
            time=int(timestamps[i].timestamp()),
            open=float(row["Open"]),
            high=float(row["High"]),
            low=float(row["Low"]),
            close=float(row["Close"]),
            volume=float(row["Volume"]),
        )
        for i, row in enumerate(df_page.to_dict("records"))
    ]
    return PaginatedOHLCV(data=bars, total=total, offset=offset, limit=limit)


@app.get("/api/v1/compare", response_model=dict[str, list[CompareBar]], tags=["data"])
@app.get("/api/compare", response_model=dict[str, list[CompareBar]], include_in_schema=False)
async def compare(
    tickers: str = Query(default="QQQ,USO,XOM", max_length=200),
    days: ValidDays = 90,
) -> dict[str, list[CompareBar]]:
    symbols = [t.strip().upper() for t in tickers.split(",") if t.strip()]
    if len(symbols) > 10:
        raise HTTPException(status_code=400, detail="Max 10 tickers allowed")

    for sym in symbols:
        if sym not in CORE_SYMBOLS and not has_parquet_data(sym):
            raise HTTPException(status_code=400, detail=f"Unknown symbol: {sym}. No Parquet data found.")

    loop = asyncio.get_event_loop()

    async def fetch_compare(sym: str) -> tuple[str, list[CompareBar]]:
        df = await loop.run_in_executor(None, get_daily, sym, days)
        if df.empty:
            return sym, []
        timestamps = pd.DatetimeIndex(df.index)
        bars = [
            CompareBar(
                date=str(timestamps[i].date()),
                time=int(timestamps[i].timestamp()),
                close=float(row["Close"]),
            )
            for i, row in enumerate(df.to_dict("records"))
        ]
        return sym, bars

    results = await asyncio.gather(*(fetch_compare(s) for s in symbols))
    return dict(results)


# ── Options & Backtest endpoints ─────────────────────────────────────


@app.get("/api/v1/options/expirations/{symbol}", response_model=list[str], tags=["options"])
@app.get("/api/options/expirations/{symbol}", response_model=list[str], include_in_schema=False)
async def options_expirations(symbol: ValidSymbol) -> list[str]:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, get_expirations, symbol)


@app.get("/api/v1/options/chain/{symbol}", response_model=OptionsChainSummary, tags=["options"])
@app.get("/api/options/chain/{symbol}", response_model=OptionsChainSummary, include_in_schema=False)
async def options_chain(
    symbol: ValidSymbol,
    max_expirations: int = Query(default=4, ge=1, le=12),
) -> OptionsChainSummary:
    loop = asyncio.get_event_loop()
    df = await loop.run_in_executor(None, get_options_chain_multi, symbol, max_expirations)

    if df.empty:
        return OptionsChainSummary(symbol=symbol)

    expirations_list: list[str] = []
    if "expiration" in df.columns:
        expirations_list = sorted(df["expiration"].dt.strftime("%Y-%m-%d").unique().tolist())

    calls_count = int((df["option_type"] == "c").sum()) if "option_type" in df.columns else 0
    puts_count = int((df["option_type"] == "p").sum()) if "option_type" in df.columns else 0

    return OptionsChainSummary(
        symbol=symbol,
        expirations=expirations_list,
        total_contracts=len(df),
        calls_count=calls_count,
        puts_count=puts_count,
    )


@app.get("/api/v1/options/chain/{symbol}/detail", response_model=OptionsChainDetail, tags=["options"])
@app.get("/api/options/chain/{symbol}/detail", response_model=OptionsChainDetail, include_in_schema=False)
async def options_chain_detail(
    symbol: ValidSymbol,
    expiration: str | None = Query(default=None, description="YYYY-MM-DD expiration date"),
    max_expirations: int = Query(default=4, ge=1, le=12),
) -> OptionsChainDetail:
    loop = asyncio.get_event_loop()

    if expiration:
        df = await loop.run_in_executor(None, get_options_chain, symbol, expiration)
    else:
        df = await loop.run_in_executor(None, get_options_chain_multi, symbol, max_expirations)

    if df.empty:
        return OptionsChainDetail(symbol=symbol)

    expirations_list: list[str] = []
    if "expiration" in df.columns:
        expirations_list = sorted(df["expiration"].dt.strftime("%Y-%m-%d").unique().tolist())

    calls_count = int((df["option_type"] == "c").sum()) if "option_type" in df.columns else 0
    puts_count = int((df["option_type"] == "p").sum()) if "option_type" in df.columns else 0

    contracts: list[OptionsContract] = []
    for _, row in df.iterrows():
        contracts.append(
            OptionsContract(
                option_type=row.get("option_type", "c"),
                expiration=(
                    row["expiration"].strftime("%Y-%m-%d")
                    if hasattr(row["expiration"], "strftime")
                    else str(row["expiration"])
                ),
                strike=float(row.get("strike", 0)),
                bid=float(row.get("bid", 0)),
                ask=float(row.get("ask", 0)),
                volume=int(row.get("volume", 0)),
                open_interest=int(row.get("open_interest", 0)),
                implied_volatility=float(row.get("implied_volatility", 0)),
                delta=float(row.get("delta", 0)),
                gamma=float(row.get("gamma", 0)),
                theta=float(row.get("theta", 0)),
                vega=float(row.get("vega", 0)),
                rho=float(row.get("rho", 0)),
            )
        )

    return OptionsChainDetail(
        symbol=symbol,
        expirations=expirations_list,
        total_contracts=len(df),
        calls_count=calls_count,
        puts_count=puts_count,
        contracts=contracts,
    )


@app.post("/api/v1/greeks/calculate", response_model=GreeksResponse, tags=["options"])
@app.post("/api/greeks/calculate", response_model=GreeksResponse, include_in_schema=False)
async def greeks_calculate(req: GreeksRequest) -> GreeksResponse:
    try:
        result = calculate_greeks(
            spot=req.spot,
            strike=req.strike,
            dte_days=req.dte_days,
            risk_free_rate=req.risk_free_rate,
            iv=req.iv,
            option_type=req.option_type,
        )
        return GreeksResponse(
            price=result.price,
            delta=result.delta,
            gamma=result.gamma,
            theta=result.theta,
            vega=result.vega,
            rho=result.rho,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/v1/iv/analysis/{symbol}", response_model=IVAnalysisResponse, tags=["options"])
@app.get("/api/iv/analysis/{symbol}", response_model=IVAnalysisResponse, include_in_schema=False)
async def iv_analysis(symbol: str) -> IVAnalysisResponse:
    upper_symbol = symbol.upper()
    if upper_symbol not in CORE_SYMBOLS and not has_parquet_data(upper_symbol):
        raise HTTPException(status_code=400, detail=f"Unknown symbol: {symbol}. No Parquet data found.")

    loop = asyncio.get_event_loop()
    result: IVAnalysisResult = await loop.run_in_executor(None, compute_iv_analysis, upper_symbol)

    return IVAnalysisResponse(
        symbol=result.symbol,
        spot_price=result.spot_price,
        current_atm_iv=result.current_atm_iv,
        iv_rank=result.iv_rank,
        iv_percentile=result.iv_percentile,
        iv_high_52w=result.iv_high_52w,
        iv_low_52w=result.iv_low_52w,
        skew_points=[
            IVSkewPointModel(
                strike=p.strike,
                implied_volatility=p.implied_volatility,
                option_type=p.option_type,
                moneyness=p.moneyness,
            )
            for p in result.skew_points
        ],
        put_call_skew=result.put_call_skew,
        term_structure=[
            IVTermPointModel(
                expiration=t.expiration,
                dte_days=t.dte_days,
                atm_iv=t.atm_iv,
            )
            for t in result.term_structure
        ],
        hv_points=[
            HVPointModel(
                window_days=h.window_days,
                realized_vol=h.realized_vol,
                label=h.label,
            )
            for h in result.hv_points
        ],
        iv_rv_spread=result.iv_rv_spread,
        error=result.error,
    )


@app.get("/api/v1/fundamentals/{symbol}", response_model=FundamentalAnalysisResponse, tags=["options"])
@app.get("/api/fundamentals/{symbol}", response_model=FundamentalAnalysisResponse, include_in_schema=False)
async def fundamental_analysis(symbol: str) -> FundamentalAnalysisResponse:
    upper_symbol = symbol.upper()

    loop = asyncio.get_event_loop()
    result: FundamentalAnalysisResult = await loop.run_in_executor(None, compute_fundamental_analysis, upper_symbol)

    return FundamentalAnalysisResponse(
        symbol=result.symbol,
        spot_price=result.spot_price,
        currency=result.currency,
        valuation=ValuationMetricsModel(
            market_cap=result.valuation.market_cap,
            trailing_pe=result.valuation.trailing_pe,
            forward_pe=result.valuation.forward_pe,
            trailing_eps=result.valuation.trailing_eps,
            forward_eps=result.valuation.forward_eps,
            price_to_book=result.valuation.price_to_book,
            price_to_sales=result.valuation.price_to_sales,
            peg_ratio=result.valuation.peg_ratio,
            enterprise_value=result.valuation.enterprise_value,
            ev_to_ebitda=result.valuation.ev_to_ebitda,
            dividend_yield=result.valuation.dividend_yield,
            beta=result.valuation.beta,
        ),
        analyst_rating=AnalystRatingModel(
            recommendation_key=result.analyst_rating.recommendation_key,
            recommendation_mean=result.analyst_rating.recommendation_mean,
            strong_buy=result.analyst_rating.strong_buy,
            buy=result.analyst_rating.buy,
            hold=result.analyst_rating.hold,
            sell=result.analyst_rating.sell,
            strong_sell=result.analyst_rating.strong_sell,
            number_of_analysts=result.analyst_rating.number_of_analysts,
        ),
        price_target=PriceTargetModel(
            current=result.price_target.current,
            low=result.price_target.low,
            high=result.price_target.high,
            mean=result.price_target.mean,
            median=result.price_target.median,
            number_of_analysts=result.price_target.number_of_analysts,
        ),
        short_interest=ShortInterestModel(
            short_ratio=result.short_interest.short_ratio,
            short_pct_of_float=result.short_interest.short_pct_of_float,
            shares_short=result.short_interest.shares_short,
        ),
        income=IncomeHighlightsModel(
            revenue=result.income.revenue,
            revenue_growth=result.income.revenue_growth,
            gross_margin=result.income.gross_margin,
            operating_margin=result.income.operating_margin,
            profit_margin=result.income.profit_margin,
            earnings_growth=result.income.earnings_growth,
        ),
        earnings_surprises=[
            EarningsSurpriseModel(
                date=e.date,
                eps_estimate=e.eps_estimate,
                eps_actual=e.eps_actual,
                surprise_pct=e.surprise_pct,
            )
            for e in result.earnings_surprises
        ],
        upgrades_downgrades=[
            UpgradeDowngradeModel(
                date=u.date,
                firm=u.firm,
                to_grade=u.to_grade,
                from_grade=u.from_grade,
                action=u.action,
            )
            for u in result.upgrades_downgrades
        ],
        next_earnings_date=result.next_earnings_date,
        error=result.error,
    )


@app.get("/api/v1/options/put-call-ratio/{symbol}", response_model=PutCallRatioResponse, tags=["options"])
@app.get("/api/options/put-call-ratio/{symbol}", response_model=PutCallRatioResponse, include_in_schema=False)
async def put_call_ratio(symbol: str) -> PutCallRatioResponse:
    upper_symbol = symbol.upper()
    if upper_symbol not in CORE_SYMBOLS and not has_parquet_data(upper_symbol):
        raise HTTPException(status_code=400, detail=f"Unknown symbol: {symbol}. No Parquet data found.")

    loop = asyncio.get_event_loop()
    result: PutCallRatioResult = await loop.run_in_executor(None, compute_put_call_ratio, upper_symbol)

    return PutCallRatioResponse(
        symbol=result.symbol,
        spot_price=result.spot_price,
        total_call_volume=result.total_call_volume,
        total_put_volume=result.total_put_volume,
        total_call_oi=result.total_call_oi,
        total_put_oi=result.total_put_oi,
        pcr_volume=result.pcr_volume,
        pcr_oi=result.pcr_oi,
        atm_pcr_volume=result.atm_pcr_volume,
        atm_pcr_oi=result.atm_pcr_oi,
        signal=result.signal,
        signal_description=result.signal_description,
        strike_points=[
            PCRStrikePointModel(
                strike=p.strike,
                call_volume=p.call_volume,
                put_volume=p.put_volume,
                call_oi=p.call_oi,
                put_oi=p.put_oi,
                pcr_volume=p.pcr_volume,
                pcr_oi=p.pcr_oi,
                moneyness=p.moneyness,
            )
            for p in result.strike_points
        ],
        term_structure=[
            PCRTermPointModel(
                expiration=t.expiration,
                dte_days=t.dte_days,
                call_volume=t.call_volume,
                put_volume=t.put_volume,
                call_oi=t.call_oi,
                put_oi=t.put_oi,
                pcr_volume=t.pcr_volume,
                pcr_oi=t.pcr_oi,
            )
            for t in result.term_structure
        ],
        expirations_analysed=result.expirations_analysed,
        error=result.error,
    )


@app.get("/api/v1/options/unusual-volume/{symbol}", response_model=UnusualVolumeResponse, tags=["options"])
@app.get("/api/options/unusual-volume/{symbol}", response_model=UnusualVolumeResponse, include_in_schema=False)
async def unusual_volume(symbol: str) -> UnusualVolumeResponse:
    upper_symbol = symbol.upper()

    loop = asyncio.get_event_loop()
    result: UnusualVolumeResult = await loop.run_in_executor(None, compute_unusual_volume, upper_symbol)

    return UnusualVolumeResponse(
        symbol=result.symbol,
        spot_price=result.spot_price,
        total_contracts_scanned=result.total_contracts_scanned,
        unusual_strikes_found=result.unusual_strikes_found,
        total_unusual_premium=result.total_unusual_premium,
        signal=result.signal,
        signal_description=result.signal_description,
        score=result.score,
        strikes=[
            UnusualStrikeModel(
                expiration=s.expiration,
                dte_days=s.dte_days,
                strike=s.strike,
                option_type=s.option_type,
                volume=s.volume,
                open_interest=s.open_interest,
                voi_ratio=s.voi_ratio,
                bid=s.bid,
                ask=s.ask,
                mid_price=s.mid_price,
                implied_volatility=s.implied_volatility,
                premium=s.premium,
                moneyness=s.moneyness,
                size_category=s.size_category,
            )
            for s in result.strikes
        ],
        cluster=(
            ClusterSummaryModel(
                is_clustered=result.cluster.is_clustered,
                pattern=result.cluster.pattern,
                unusual_call_count=result.cluster.unusual_call_count,
                unusual_put_count=result.cluster.unusual_put_count,
                total_premium=result.cluster.total_premium,
                total_contracts=result.cluster.total_contracts,
            )
            if result.cluster
            else None
        ),
        expirations_scanned=result.expirations_scanned,
        error=result.error,
    )


@app.post("/api/v1/backtest", response_model=BacktestResponse, tags=["options"])
@app.post("/api/backtest", response_model=BacktestResponse, include_in_schema=False)
async def run_backtest_endpoint(req: BacktestRequest) -> BacktestResponse:
    upper_symbol = req.symbol.upper()
    if upper_symbol not in CORE_SYMBOLS and not has_parquet_data(upper_symbol):
        raise HTTPException(status_code=400, detail=f"Unknown symbol: {req.symbol}. No Parquet data found.")

    try:
        strategy_type = StrategyType(req.strategy)
    except ValueError:
        valid = [s.value for s in StrategyType]
        raise HTTPException(status_code=400, detail=f"Unknown strategy: {req.strategy}. Valid: {valid}")

    loop = asyncio.get_event_loop()

    daily_data = await loop.run_in_executor(None, get_daily, upper_symbol, 365)

    source = get_options_source("synthetic")
    options_data = await loop.run_in_executor(
        None,
        lambda: source.get_historical_chain(upper_symbol, daily_data),
    )

    if options_data.empty:
        return BacktestResponse(
            symbol=upper_symbol,
            strategy=req.strategy,
            metrics=BacktestMetrics(),
            error="No options data available for this symbol",
        )

    stock_data = pd.DataFrame()
    if not daily_data.empty:
        stock_data = pd.DataFrame(
            {
                "underlying_symbol": upper_symbol,
                "quote_date": pd.DatetimeIndex(daily_data.index),
                "close": daily_data["Close"].values,
            }
        )

    config = BacktestConfig(
        strategy_type=strategy_type,
        max_entry_dte=req.max_entry_dte,
        exit_dte=req.exit_dte,
        leg1_delta=req.leg1_delta,
        leg2_delta=req.leg2_delta,
        capital=req.capital,
        quantity=req.quantity,
        max_positions=req.max_positions,
        commission_per_contract=req.commission_per_contract,
        stop_loss=req.stop_loss,
        take_profit=req.take_profit,
    )

    bt_result = await loop.run_in_executor(None, run_backtest, options_data, stock_data, config, None)

    metrics = BacktestMetrics(
        total_trades=bt_result.total_trades,
        win_rate=bt_result.win_rate,
        mean_return=bt_result.mean_return,
        sharpe_ratio=bt_result.sharpe_ratio,
        sortino_ratio=bt_result.sortino_ratio,
        max_drawdown=bt_result.max_drawdown,
        profit_factor=bt_result.profit_factor,
        calmar_ratio=bt_result.calmar_ratio,
        final_equity=bt_result.final_equity,
    )

    return BacktestResponse(
        symbol=upper_symbol,
        strategy=req.strategy,
        metrics=metrics,
        equity_curve=bt_result.equity_curve,
        trade_count=bt_result.total_trades,
        error=bt_result.error,
    )


# ── Multi-leg strategy analysis ──────────────────────────────────────


@app.post("/api/v1/options/multi-leg/analyze", tags=["options"], response_model=MultiLegResponse)
async def analyze_multi_leg_strategy(req: MultiLegRequest) -> MultiLegResponse:
    loop = asyncio.get_running_loop()

    legs = [
        OptionLeg(
            option_type=leg.option_type,
            action=leg.action,
            strike=leg.strike,
            expiration=leg.expiration,
            quantity=leg.quantity,
            premium=leg.premium,
            iv=leg.iv,
        )
        for leg in req.legs
    ]

    try:
        result = await loop.run_in_executor(
            None,
            lambda: analyze_multi_leg(
                legs=legs,
                spot=req.spot,
                dte_days=req.dte_days,
                risk_free_rate=req.risk_free_rate,
            ),
        )
    except ValueError as exc:
        return MultiLegResponse(error=str(exc))

    return MultiLegResponse(
        net_debit_credit=result.net_debit_credit,
        max_profit=result.max_profit,
        max_loss=result.max_loss,
        breakeven_points=result.breakeven_points,
        greeks=AggregatedGreeksModel(
            delta=result.greeks.delta,
            gamma=result.greeks.gamma,
            theta=result.greeks.theta,
            vega=result.greeks.vega,
            rho=result.greeks.rho,
        ),
        pnl_curve=[PnLPointModel(price=p.price, pnl=p.pnl) for p in result.pnl_curve],
    )


# ── AI Interpretation (Ollama streaming) ─────────────────────────────


class BacktestInterpretRequest(BaseModel):
    """Payload for AI-driven backtest interpretation."""

    symbol: str
    strategy: str
    trade_count: int
    metrics: dict[str, float]
    equity_curve_summary: str = Field(
        default="",
        description="Optional summary of equity curve shape (e.g. 'uptrend with 15% drawdown mid-period')",
    )


def _build_interpret_prompt(req: BacktestInterpretRequest) -> str:
    """Build a structured prompt for the Ollama model."""
    metrics_text = "\n".join(f"  - {k}: {v}" for k, v in req.metrics.items())
    return (
        "You are an expert options trading analyst. "
        "Analyze the following backtest results and provide a concise, actionable interpretation. "
        "Output in bilingual format: Chinese first, then English.\n\n"
        f"## Backtest Summary\n"
        f"- Symbol: {req.symbol}\n"
        f"- Strategy: {req.strategy}\n"
        f"- Total Trades: {req.trade_count}\n"
        f"- Metrics:\n{metrics_text}\n"
        + (f"- Equity Curve: {req.equity_curve_summary}\n" if req.equity_curve_summary else "")
        + "\n"
        "## Required Analysis\n"
        "1. Overall assessment (is this strategy profitable and robust?)\n"
        "2. Risk analysis (drawdown, Sharpe, Sortino interpretation)\n"
        "3. Key strengths and weaknesses\n"
        "4. Actionable suggestions for improvement\n\n"
        "Keep it concise (under 500 words total). Use bullet points."
    )


@app.post("/api/v1/backtest/interpret", tags=["options"])
async def interpret_backtest(req: BacktestInterpretRequest) -> StreamingResponse:
    """Stream AI interpretation of backtest results via Ollama."""
    prompt = _build_interpret_prompt(req)

    async def generate() -> AsyncIterator[str]:
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(connect=10.0, read=120.0, write=10.0, pool=10.0)
            ) as client:
                async with client.stream(
                    "POST",
                    f"{settings.ollama_base_url}/api/generate",
                    json={"model": settings.ollama_model, "prompt": prompt, "stream": True},
                ) as resp:
                    if resp.status_code != 200:
                        yield f'data: {{"error": "Ollama returned {resp.status_code}"}}\n\n'
                        return
                    async for line in resp.aiter_lines():
                        if not line:
                            continue
                        try:
                            chunk = _json.loads(line)
                        except _json.JSONDecodeError:
                            continue
                        token = chunk.get("response", "")
                        if token:
                            yield f"data: {_json.dumps({'token': token})}\n\n"
                        if chunk.get("done"):
                            yield 'data: {"done": true}\n\n'
                            return
        except httpx.ConnectError:
            yield 'data: {"error": "Cannot connect to Ollama. Is it running?"}\n\n'
        except Exception as exc:
            yield f'data: {{"error": "{str(exc)[:200]}"}}\n\n'

    return StreamingResponse(generate(), media_type="text/event-stream")


# ── Signal backtest endpoints ────────────────────────────────────────


@app.post(
    "/api/v1/backtest/signals",
    response_model=SignalBacktestResponse,
    tags=["signal-backtest"],
)
async def signal_backtest(req: SignalBacktestRequest) -> SignalBacktestResponse:
    symbol = validate_symbol(req.symbol)
    result = await asyncio.to_thread(
        run_signal_backtest,
        symbol=symbol,
        start_date=req.start_date,
        end_date=req.end_date,
        horizons=req.horizons,
    )
    return result


@app.post(
    "/api/v1/backtest/walk-forward",
    response_model=WalkForwardResponse,
    tags=["signal-backtest"],
)
async def walk_forward(req: WalkForwardRequest) -> WalkForwardResponse:
    symbol = validate_symbol(req.symbol)
    result = await asyncio.to_thread(
        run_walk_forward,
        symbol=symbol,
        train_days=req.train_days,
        test_days=req.test_days,
        step_days=req.step_days,
        horizon=req.horizon,
    )
    return result


# ── Position management endpoints ────────────────────────────────────


def _position_to_response(pos: Position, current_price: float | None = None) -> PositionResponse:
    unreal = calc_unrealized_pnl(pos, current_price) if current_price is not None and pos.status == "open" else None
    real = calc_realized_pnl(pos) if pos.status == "closed" else None
    cost = calc_total_cost(pos)

    return PositionResponse(
        id=pos.id,
        symbol=pos.symbol,
        option_type=pos.option_type,
        strike=pos.strike,
        expiration=pos.expiration,
        quantity=pos.quantity,
        entry_price=pos.entry_price,
        entry_date=pos.entry_date,
        entry_commission=pos.entry_commission,
        exit_price=pos.exit_price,
        exit_date=pos.exit_date,
        exit_commission=pos.exit_commission,
        status=pos.status,
        delta=pos.delta,
        gamma=pos.gamma,
        theta=pos.theta,
        vega=pos.vega,
        rho=pos.rho,
        strategy_name=pos.strategy_name,
        tags=pos.tags,
        notes=pos.notes,
        created_at=pos.created_at,
        updated_at=pos.updated_at,
        unrealized_pnl=unreal,
        realized_pnl=real,
        total_cost=cost,
    )


@app.post("/api/v1/positions", response_model=PositionResponse, tags=["positions"], status_code=201)
async def create_position_endpoint(req: PositionCreate, _api_key: ApiKey) -> PositionResponse:
    if req.quantity == 0:
        raise HTTPException(status_code=400, detail="quantity cannot be 0")
    async with get_session() as session:
        pos = await create_position(
            session,
            symbol=req.symbol,
            option_type=req.option_type,
            strike=req.strike,
            expiration=req.expiration,
            quantity=req.quantity,
            entry_price=req.entry_price,
            entry_date=req.entry_date,
            entry_commission=req.entry_commission,
            strategy_name=req.strategy_name,
            tags=req.tags,
            notes=req.notes,
        )
        return _position_to_response(pos)


@app.get("/api/v1/positions", response_model=list[PositionResponse], tags=["positions"])
async def list_positions_endpoint(
    _api_key: ApiKey,
    status: str | None = Query(default=None, pattern=r"^(open|closed|expired)$"),
    symbol: str | None = Query(default=None),
    strategy: str | None = Query(default=None),
) -> list[PositionResponse]:
    async with get_session() as session:
        positions = await list_positions(session, status=status, symbol=symbol, strategy_name=strategy)
        return [_position_to_response(p) for p in positions]


@app.get("/api/v1/positions/{position_id}", response_model=PositionResponse, tags=["positions"])
async def get_position_endpoint(position_id: str, _api_key: ApiKey) -> PositionResponse:
    async with get_session() as session:
        pos = await get_position(session, position_id)
        if pos is None:
            raise HTTPException(status_code=404, detail=f"Position {position_id} not found")
        return _position_to_response(pos)


@app.put("/api/v1/positions/{position_id}", response_model=PositionResponse, tags=["positions"])
async def update_position_endpoint(position_id: str, req: PositionUpdate, _api_key: ApiKey) -> PositionResponse:
    async with get_session() as session:
        updates = {k: v for k, v in req.model_dump().items() if v is not None}
        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")
        pos = await update_position(session, position_id, **updates)
        if pos is None:
            raise HTTPException(status_code=404, detail=f"Position {position_id} not found")
        return _position_to_response(pos)


@app.post("/api/v1/positions/{position_id}/close", response_model=PositionResponse, tags=["positions"])
async def close_position_endpoint(position_id: str, req: PositionClose, _api_key: ApiKey) -> PositionResponse:
    async with get_session() as session:
        try:
            pos = await close_position(
                session,
                position_id,
                exit_price=req.exit_price,
                exit_commission=req.exit_commission,
                exit_date=req.exit_date,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        if pos is None:
            raise HTTPException(status_code=404, detail=f"Position {position_id} not found")
        return _position_to_response(pos)


@app.delete("/api/v1/positions/{position_id}", tags=["positions"], status_code=204)
async def delete_position_endpoint(position_id: str, _api_key: ApiKey) -> Response:
    async with get_session() as session:
        deleted = await delete_position(session, position_id)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Position {position_id} not found")
        return Response(status_code=204)


@app.get("/api/v1/portfolio/summary", response_model=PortfolioSummaryResponse, tags=["positions"])
async def portfolio_summary(_api_key: ApiKey) -> PortfolioSummaryResponse:
    async with get_session() as session:
        all_positions = await list_positions(session)

        open_positions = [p for p in all_positions if p.status == "open"]
        closed_positions = [p for p in all_positions if p.status == "closed"]
        expired_positions = [p for p in all_positions if p.status == "expired"]

        total_realized = sum(calc_realized_pnl(p) for p in closed_positions)
        total_cost = sum(calc_total_cost(p) for p in open_positions)
        greeks = aggregate_greeks(open_positions)

        return PortfolioSummaryResponse(
            total_positions=len(all_positions),
            open_positions=len(open_positions),
            closed_positions=len(closed_positions),
            expired_positions=len(expired_positions),
            total_unrealized_pnl=0.0,
            total_realized_pnl=total_realized,
            total_cost=total_cost,
            greeks=AggregatedGreeksModel(**greeks),
        )


@app.get("/api/v1/portfolio/strategies", response_model=list[StrategyGroupResponse], tags=["positions"])
async def portfolio_by_strategy(_api_key: ApiKey) -> list[StrategyGroupResponse]:
    async with get_session() as session:
        all_positions = await list_positions(session)
        groups = group_by_strategy(all_positions)

        result: list[StrategyGroupResponse] = []
        for name, positions in groups.items():
            open_count = sum(1 for p in positions if p.status == "open")
            total_realized = sum(calc_realized_pnl(p) for p in positions if p.status == "closed")
            result.append(
                StrategyGroupResponse(
                    strategy_name=name,
                    position_count=len(positions),
                    open_count=open_count,
                    total_realized_pnl=total_realized,
                    positions=[_position_to_response(p) for p in positions],
                )
            )
        return result


@app.get("/api/v1/positions/alerts/expiring", response_model=list[PositionResponse], tags=["positions"])
async def expiring_positions(_api_key: ApiKey, days: int = Query(default=7, ge=1, le=90)) -> list[PositionResponse]:
    async with get_session() as session:
        positions = await get_expiring_positions(session, days_ahead=days)
        return [_position_to_response(p) for p in positions]


@app.post("/api/v1/positions/batch/mark-expired", tags=["positions"])
async def batch_mark_expired(_api_key: ApiKey) -> dict[str, int]:
    async with get_session() as session:
        count = await mark_expired_positions(session)
        return {"marked_expired": count}


# ── ML-enhanced endpoints ────────────────────────────────────────────


@app.get("/api/v1/signals/enhanced", response_model=list[EnhancedSignal], tags=["ml"])
async def get_enhanced_signals(
    regime_engine: RegimeEngine,
    strategy_engine: StratEngine,
    ml_regime: MLRegime,
    ml_scorer: MLScorer,
) -> list[EnhancedSignal]:
    loop = asyncio.get_event_loop()
    regime = await loop.run_in_executor(None, regime_engine.evaluate)

    async def eval_enhanced(sym: str) -> EnhancedSignal:
        signal = await loop.run_in_executor(None, strategy_engine.evaluate_symbol, sym, regime)
        daily = await loop.run_in_executor(None, get_daily, sym, 120)

        ml_confidence = 0.0
        combined_score = 0.0
        feature_importance: dict[str, float] = {}
        ml_regime_label: str = regime.regime.value
        regime_probs: dict[str, float] = {}

        if ml_regime.is_trained:
            try:
                qqq = await loop.run_in_executor(None, get_daily, settings.market_index, 120)
                vix = await loop.run_in_executor(None, get_daily, settings.volatility_index, 120)
                pred = await loop.run_in_executor(None, ml_regime.predict, qqq, vix)
                ml_regime_label = pred.regime
                regime_probs = pred.probabilities
            except Exception:
                logger.warning("ML regime prediction failed for %s, using rule-based", sym)

        if ml_scorer.is_trained and not daily.empty:
            try:
                result = await loop.run_in_executor(None, ml_scorer.predict, daily, signal.score)
                ml_confidence = result.ml_probability
                combined_score = result.combined_score
                feature_importance = result.feature_importance
            except Exception:
                logger.warning("ML scoring failed for %s", sym)

        return EnhancedSignal(
            symbol=signal.symbol,
            bias=signal.bias,
            level=signal.level.value if isinstance(signal.level, SignalLevel) else signal.level,
            action=signal.action,
            rationale=signal.rationale,
            price=signal.price,
            trigger_price=signal.trigger_price,
            option_structure=signal.option_structure,
            option_hint=signal.option_hint,
            timestamp=signal.timestamp,
            score=signal.score,
            ml_confidence=ml_confidence,
            ml_regime=ml_regime_label,
            regime_probabilities=regime_probs,
            feature_importance=feature_importance,
            combined_score=combined_score,
        )

    results = await asyncio.gather(*(eval_enhanced(s) for s in settings.symbols))
    return list(results)


@app.get("/api/v1/ml/regime", response_model=MLRegimeResponse, tags=["ml"])
async def get_ml_regime(regime_engine: RegimeEngine, ml_regime: MLRegime) -> MLRegimeResponse:
    loop = asyncio.get_event_loop()

    if not ml_regime.is_trained:
        rule_regime = await loop.run_in_executor(None, regime_engine.evaluate)
        return MLRegimeResponse(regime=rule_regime.regime, source="rule_based")

    qqq = await loop.run_in_executor(None, get_daily, settings.market_index, 120)
    vix = await loop.run_in_executor(None, get_daily, settings.volatility_index, 120)
    pred = await loop.run_in_executor(None, ml_regime.predict, qqq, vix)

    return MLRegimeResponse(
        regime=pred.regime,
        probabilities=pred.probabilities,
        state=pred.state,
        source=pred.source,
    )


@app.post("/api/v1/ml/train", response_model=TrainingStatusResponse, tags=["ml"])
async def trigger_training(req: TrainingRequest, _api_key: ApiKey) -> TrainingStatusResponse:
    regime_clf = get_regime_classifier()
    scorer = get_signal_scorer()

    loop = asyncio.get_event_loop()
    status: TrainingStatus = await loop.run_in_executor(
        None, run_training_pipeline, regime_clf, scorer, req.lookback_days
    )

    return TrainingStatusResponse(
        last_trained=status.last_trained,
        regime_metrics=status.regime_metrics,
        scorer_metrics=status.scorer_metrics,
        symbols_trained=status.symbols_trained,
        error=status.error,
        regime_model_available=regime_clf.is_trained,
        scorer_model_available=scorer.is_trained,
    )


@app.get("/api/v1/ml/status", response_model=TrainingStatusResponse, tags=["ml"])
async def get_ml_status(ml_regime: MLRegime, ml_scorer: MLScorer) -> TrainingStatusResponse:
    loop = asyncio.get_event_loop()
    status: TrainingStatus = await loop.run_in_executor(None, load_status)

    return TrainingStatusResponse(
        last_trained=status.last_trained,
        regime_metrics=status.regime_metrics,
        scorer_metrics=status.scorer_metrics,
        symbols_trained=status.symbols_trained,
        error=status.error,
        regime_model_available=ml_regime.is_trained,
        scorer_model_available=ml_scorer.is_trained,
    )


@app.post("/api/v1/ml/analyze/{symbol}", tags=["ml"])
async def analyze_signal(
    symbol: ValidSymbol,
    regime_engine: RegimeEngine,
    strategy_engine: StratEngine,
    ml_regime: MLRegime,
    ml_scorer: MLScorer,
) -> StreamingResponse:
    loop = asyncio.get_event_loop()
    regime = await loop.run_in_executor(None, regime_engine.evaluate)
    signal = await loop.run_in_executor(None, strategy_engine.evaluate_symbol, symbol, regime)
    daily = await loop.run_in_executor(None, get_daily, symbol, 120)

    ml_confidence = 0.0
    ml_regime_label: str = regime.regime.value
    feature_importance: dict[str, float] = {}

    if ml_regime.is_trained:
        try:
            qqq = await loop.run_in_executor(None, get_daily, settings.market_index, 120)
            vix = await loop.run_in_executor(None, get_daily, settings.volatility_index, 120)
            pred = await loop.run_in_executor(None, ml_regime.predict, qqq, vix)
            ml_regime_label = pred.regime
        except Exception:
            pass

    if ml_scorer.is_trained and not daily.empty:
        try:
            result = await loop.run_in_executor(None, ml_scorer.predict, daily, signal.score)
            ml_confidence = result.ml_probability
            feature_importance = result.feature_importance
        except Exception:
            pass

    base_signal: dict[str, object] = {
        "bias": signal.bias,
        "level": signal.level.value if isinstance(signal.level, SignalLevel) else signal.level,
        "score": signal.score,
        "action": signal.action,
        "option_structure": signal.option_structure,
    }

    async def generate() -> AsyncIterator[str]:
        async for chunk in stream_signal_analysis(
            symbol=symbol,
            base_signal=base_signal,
            ml_confidence=ml_confidence,
            ml_regime=ml_regime_label,
            feature_importance=feature_importance,
        ):
            yield f"data: {chunk}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


# ── Symbol Discovery ─────────────────────────────────────────────────


@app.get("/api/v1/symbols/available", response_model=list[str], tags=["discovery"])
async def get_available() -> list[str]:
    loop = asyncio.get_event_loop()
    symbols = await loop.run_in_executor(None, get_available_symbols)
    return sorted(symbols)


@app.get("/api/v1/symbols/search", response_model=PaginatedSymbolResult, tags=["discovery"])
async def search_symbols_endpoint(
    query: str | None = Query(default=None, description="Substring match on symbol"),
    min_volume: float | None = Query(default=None, ge=0, description="Minimum average volume"),
    min_rows: int | None = Query(default=None, ge=1, description="Minimum data rows"),
    sort_by: str = Query(default="symbol", pattern="^(symbol|volume|rows|return|last_close)$"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> PaginatedSymbolResult:
    loop = asyncio.get_event_loop()
    items, total = await loop.run_in_executor(None, search_symbols, query, min_volume, min_rows, sort_by, limit, offset)
    return PaginatedSymbolResult(
        items=[
            SymbolMetaResponse(
                symbol=m.symbol,
                rows=m.rows,
                first_date=m.first_date,
                last_date=m.last_date,
                avg_volume=m.avg_volume,
                last_close=m.last_close,
                return_1y=m.return_1y,
            )
            for m in items
        ],
        total=total,
        offset=offset,
        limit=limit,
    )


@app.get("/api/v1/symbols/metadata", response_model=list[SymbolMetaResponse], tags=["discovery"])
async def get_all_metadata() -> list[SymbolMetaResponse]:
    loop = asyncio.get_event_loop()
    index = await loop.run_in_executor(None, build_metadata_index)
    return [
        SymbolMetaResponse(
            symbol=m.symbol,
            rows=m.rows,
            first_date=m.first_date,
            last_date=m.last_date,
            avg_volume=m.avg_volume,
            last_close=m.last_close,
            return_1y=m.return_1y,
        )
        for m in index
    ]


# ── Broker / Trading ─────────────────────────────────────────────────

BrokerDep = Annotated[AlpacaBroker, Depends(get_broker)]


@app.get("/api/v1/broker/account", response_model=AccountInfoResponse, tags=["broker"])
async def broker_account(broker: BrokerDep, _api_key: ApiKey) -> AccountInfoResponse:
    return await asyncio.to_thread(broker.get_account)


@app.post("/api/v1/broker/orders", response_model=OrderResponse, tags=["broker"])
async def broker_submit_order(req: CreateOrderRequest, broker: BrokerDep, _api_key: ApiKey) -> OrderResponse:
    try:
        return await asyncio.to_thread(broker.submit_order, req)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Alpaca API error: {exc}") from exc


@app.get("/api/v1/broker/orders", response_model=list[OrderResponse], tags=["broker"])
async def broker_list_orders(
    broker: BrokerDep,
    _api_key: ApiKey,
    status: str = Query(default="open", pattern="^(open|closed|all)$"),
    limit: int = Query(default=50, ge=1, le=500),
    symbols: str | None = Query(default=None, description="Comma-separated symbols"),
) -> list[OrderResponse]:
    sym_list = [s.strip().upper() for s in symbols.split(",")] if symbols else None
    return await asyncio.to_thread(broker.get_orders, status, limit, sym_list)


@app.delete("/api/v1/broker/orders/{order_id}", tags=["broker"])
async def broker_cancel_order(order_id: str, broker: BrokerDep, _api_key: ApiKey) -> dict[str, str]:
    try:
        await asyncio.to_thread(broker.cancel_order, order_id)
        return {"status": "cancelled", "order_id": order_id}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Alpaca API error: {exc}") from exc


@app.delete("/api/v1/broker/orders", tags=["broker"])
async def broker_cancel_all_orders(broker: BrokerDep, _api_key: ApiKey) -> dict[str, int]:
    count = await asyncio.to_thread(broker.cancel_all_orders)
    return {"cancelled": count}


@app.get("/api/v1/broker/positions", response_model=list[BrokerPositionResponse], tags=["broker"])
async def broker_list_positions(broker: BrokerDep, _api_key: ApiKey) -> list[BrokerPositionResponse]:
    return await asyncio.to_thread(broker.get_positions)


@app.get("/api/v1/broker/positions/{symbol}", response_model=BrokerPositionResponse, tags=["broker"])
async def broker_get_position(symbol: str, broker: BrokerDep, _api_key: ApiKey) -> BrokerPositionResponse:
    try:
        return await asyncio.to_thread(broker.get_position, symbol)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"No position for {symbol}: {exc}") from exc


@app.delete("/api/v1/broker/positions/{symbol}", response_model=OrderResponse, tags=["broker"])
async def broker_close_position(
    symbol: str,
    broker: BrokerDep,
    _api_key: ApiKey,
    req: BrokerClosePositionRequest | None = None,
) -> OrderResponse:
    try:
        return await asyncio.to_thread(broker.close_position, symbol, req)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to close {symbol}: {exc}") from exc


@app.delete("/api/v1/broker/positions", tags=["broker"])
async def broker_close_all_positions(broker: BrokerDep, _api_key: ApiKey) -> dict[str, int]:
    count = await asyncio.to_thread(broker.close_all_positions)
    return {"closed": count}


@app.post("/api/v1/broker/portfolio/history", response_model=PortfolioHistoryResponse, tags=["broker"])
async def broker_portfolio_history(
    req: PortfolioHistoryRequest, broker: BrokerDep, _api_key: ApiKey
) -> PortfolioHistoryResponse:
    return await asyncio.to_thread(broker.get_portfolio_history, req)


# ── WebSocket ────────────────────────────────────────────────────────


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    client_id = uuid.uuid4().hex[:12]
    await ws_manager.connect(ws, client_id)
    try:
        while True:
            raw = await ws.receive_text()
            await handle_client_message(client_id, raw)
    except Exception:
        pass
    finally:
        ws_manager.disconnect(client_id)
