"""FastAPI server — REST API for the web dashboard.

Start:
    uvicorn app.server:app --port 8300 --reload
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections import defaultdict
from contextlib import asynccontextmanager
from functools import lru_cache
from typing import Annotated, AsyncIterator

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
from pydantic import BaseModel, Field

from app.config import settings
from app.data_provider import clear_cache as clear_data_cache, get_daily, get_intraday
from app.indicators import atr, prev_day_high, prev_day_low, rolling_high, rolling_low, session_vwap, sma
from app.market_regime import MarketRegimeEngine
from app.models import MarketRegimeResult, Signal, SignalLevel
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
    logger.info("Signal system API shutting down")


tags_metadata = [
    {"name": "health", "description": "Health & status checks"},
    {"name": "market", "description": "Market regime & signal endpoints"},
    {"name": "data", "description": "OHLCV & indicator data"},
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
    allow_methods=["GET"],
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
