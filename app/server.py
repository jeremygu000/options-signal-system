"""FastAPI server — REST API for the web dashboard.

Start:
    uvicorn app.server:app --port 8200 --reload
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
from pydantic import BaseModel

from app.config import settings
from app.data_provider import get_daily, get_intraday
from app.indicators import atr, prev_day_high, prev_day_low, rolling_high, rolling_low, session_vwap, sma
from app.market_regime import MarketRegimeEngine
from app.models import MarketRegimeResult, Signal, SignalLevel
from app.strategy_engine import StrategyEngine

logger = logging.getLogger(__name__)


# ── Response models ──────────────────────────────────────────────────


class HealthResponse(BaseModel):
    status: str
    timestamp: str


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


# ── App ──────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
    logger.info("Signal system API started on port 8200")
    yield


app = FastAPI(
    title="Options Signal System API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Endpoints ────────────────────────────────────────────────────────


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", timestamp=datetime.now().isoformat())


@app.get("/api/symbols", response_model=list[SymbolInfo])
def list_symbols() -> list[SymbolInfo]:
    """List all configured symbols with data availability."""
    all_symbols = [settings.market_index, settings.volatility_index, *settings.symbols]
    result: list[SymbolInfo] = []
    for sym in all_symbols:
        df = get_daily(sym, days=None)
        last_date = str(df.index[-1].date()) if not df.empty else ""
        result.append(
            SymbolInfo(
                symbol=sym,
                has_daily=not df.empty,
                daily_rows=len(df),
                last_date=last_date,
            )
        )
    return result


@app.get("/api/regime", response_model=MarketRegimeResult)
def get_regime() -> MarketRegimeResult:
    """Evaluate current market regime (risk_on / neutral / risk_off)."""
    engine = MarketRegimeEngine(
        qqq_symbol=settings.market_index,
        vix_symbol=settings.volatility_index,
    )
    return engine.evaluate()


@app.get("/api/signals", response_model=list[Signal])
def get_signals() -> list[Signal]:
    """Evaluate all configured symbols and return signals."""
    regime_engine = MarketRegimeEngine(
        qqq_symbol=settings.market_index,
        vix_symbol=settings.volatility_index,
    )
    strategy_engine = StrategyEngine()
    regime = regime_engine.evaluate()
    return [strategy_engine.evaluate_symbol(sym, regime) for sym in settings.symbols]


@app.get("/api/scan", response_model=FullScanResponse)
def full_scan() -> FullScanResponse:
    """Full scan — regime + all signals in one call."""
    regime_engine = MarketRegimeEngine(
        qqq_symbol=settings.market_index,
        vix_symbol=settings.volatility_index,
    )
    strategy_engine = StrategyEngine()
    regime = regime_engine.evaluate()
    signals = [strategy_engine.evaluate_symbol(sym, regime) for sym in settings.symbols]
    return FullScanResponse(
        regime=regime,
        signals=signals,
        timestamp=datetime.now().isoformat(),
    )


@app.get("/api/indicators/{symbol}", response_model=IndicatorSnapshot)
def get_indicators(symbol: str) -> IndicatorSnapshot:
    """Get current indicator values for a symbol."""
    import math

    daily = get_daily(symbol, days=60)
    intraday = get_intraday(symbol)

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
    if not intraday.empty:
        vwap_series = session_vwap(intraday)
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


@app.get("/api/ohlcv/{symbol}", response_model=list[OHLCVBar])
def get_ohlcv(symbol: str, days: int = 90) -> list[OHLCVBar]:
    """Get daily OHLCV bars for a symbol."""
    df = get_daily(symbol, days=days)
    if df.empty:
        return []

    timestamps = pd.DatetimeIndex(df.index)
    result: list[OHLCVBar] = []
    for i, (_, row) in enumerate(df.iterrows()):
        dt = timestamps[i]
        result.append(
            OHLCVBar(
                date=str(dt.date()),
                time=int(dt.timestamp()),
                open=float(row["Open"]),
                high=float(row["High"]),
                low=float(row["Low"]),
                close=float(row["Close"]),
                volume=float(row["Volume"]),
            )
        )
    return result


@app.get("/api/compare")
def compare(tickers: str = "QQQ,USO,XOM", days: int = 90) -> dict[str, list[dict[str, Any]]]:
    """Get close prices for multiple tickers (for comparison chart)."""
    symbols = [t.strip() for t in tickers.split(",") if t.strip()]
    result: dict[str, list[dict[str, Any]]] = {}
    for sym in symbols:
        df = get_daily(sym, days=days)
        if df.empty:
            result[sym] = []
            continue
        bars: list[dict[str, Any]] = []
        timestamps = pd.DatetimeIndex(df.index)
        for i, (_, row) in enumerate(df.iterrows()):
            dt = timestamps[i]
            bars.append(
                {
                    "date": str(dt.date()),
                    "time": int(dt.timestamp()),
                    "close": float(row["Close"]),
                }
            )
        result[sym] = bars
    return result
