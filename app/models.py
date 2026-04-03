"""Data models — structured output for every layer."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

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
    timestamp: datetime = Field(default_factory=datetime.now)


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
    timestamp: datetime = Field(default_factory=datetime.now)
    score: int = Field(default=0, description="Internal score used to determine signal level")
