"""FastAPI server — REST API for the web dashboard.

Start:
    uvicorn app.server:app --port 8300 --reload
"""

from __future__ import annotations

import asyncio
import json as _json
import logging
import time
import uuid
from collections import defaultdict
from contextlib import asynccontextmanager
from functools import lru_cache
from typing import Annotated, AsyncIterator

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import httpx
import pandas as pd
from pydantic import BaseModel, Field

from app.backtester import BacktestConfig, StrategyType, run_backtest, run_multi_strategy_backtest
from app.config import settings
from app.data_provider import clear_cache as clear_data_cache, get_daily, get_intraday
from app.greeks import GreeksResult, calculate_greeks
from app.indicators import atr, prev_day_high, prev_day_low, rolling_high, rolling_low, session_vwap, sma
from app.market_regime import MarketRegimeEngine
from app.models import (
    BacktestMetrics,
    BacktestRequest,
    BacktestResponse,
    MarketRegimeResult,
    OptionsChainDetail,
    OptionsChainSummary,
    OptionsContract,
    Signal,
    SignalLevel,
)
from app.options_data import clear_chain_cache, get_expirations, get_options_chain, get_options_chain_multi
from app.options_source import get_options_source
from app.strategy_engine import StrategyEngine
from app.utils import now_ny

logger = logging.getLogger(__name__)

ALLOWED_SYMBOLS: set[str] = {s.upper() for s in [settings.market_index, settings.volatility_index, *settings.symbols]}


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


def validate_symbol(symbol: str) -> str:
    upper = symbol.upper()
    if upper not in ALLOWED_SYMBOLS:
        raise HTTPException(status_code=400, detail=f"Unknown symbol: {symbol}. Allowed: {sorted(ALLOWED_SYMBOLS)}")
    return upper


def validate_days(days: int = Query(default=90, ge=1, le=365)) -> int:
    return days


ValidSymbol = Annotated[str, Depends(validate_symbol)]
ValidDays = Annotated[int, Depends(validate_days)]
RegimeEngine = Annotated[MarketRegimeEngine, Depends(get_regime_engine)]
StratEngine = Annotated[StrategyEngine, Depends(get_strategy_engine)]


# ── Rate limiter ─────────────────────────────────────────────────────

_rate_store: dict[str, list[float]] = defaultdict(list)


def _check_rate_limit(client_ip: str) -> None:
    now = time.monotonic()
    window = 60.0
    max_requests = settings.rate_limit_per_minute
    timestamps = _rate_store[client_ip]
    _rate_store[client_ip] = [t for t in timestamps if now - t < window]
    if len(_rate_store[client_ip]) >= max_requests:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    _rate_store[client_ip].append(now)


# ── App ──────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
    logger.info("Signal system API started on port 8300")
    yield
    get_regime_engine.cache_clear()
    get_strategy_engine.cache_clear()
    clear_data_cache()
    clear_chain_cache()
    logger.info("Signal system API shutting down")


tags_metadata = [
    {"name": "health", "description": "Health & status checks"},
    {"name": "market", "description": "Market regime & signal endpoints"},
    {"name": "data", "description": "OHLCV & indicator data"},
    {"name": "options", "description": "Options chain & backtesting"},
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
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_middleware(request: Request, call_next: object) -> Response:
    request_id = str(uuid.uuid4())[:8]
    request.state.request_id = request_id

    client_ip = request.client.host if request.client else "unknown"
    try:
        _check_rate_limit(client_ip)
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
        if sym not in ALLOWED_SYMBOLS:
            raise HTTPException(status_code=400, detail=f"Unknown symbol: {sym}. Allowed: {sorted(ALLOWED_SYMBOLS)}")

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


@app.post("/api/v1/backtest", response_model=BacktestResponse, tags=["options"])
@app.post("/api/backtest", response_model=BacktestResponse, include_in_schema=False)
async def run_backtest_endpoint(req: BacktestRequest) -> BacktestResponse:
    upper_symbol = req.symbol.upper()
    if upper_symbol not in ALLOWED_SYMBOLS:
        raise HTTPException(status_code=400, detail=f"Unknown symbol: {req.symbol}. Allowed: {sorted(ALLOWED_SYMBOLS)}")

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
