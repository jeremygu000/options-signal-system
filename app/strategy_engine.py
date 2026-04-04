"""Strategy engine — 对每个标的评估信号，基于评分制。

Scoring rules are explicit and tunable. Each condition contributes points.
Score thresholds determine signal level (强信号 / 观察信号 / 无信号).
"""

from __future__ import annotations

import logging
import math
from datetime import datetime

import pandas as pd

from app.config import settings
from app.data_provider import get_daily, get_intraday
from app.indicators import (
    atr,
    prev_day_high,
    prev_day_low,
    rolling_high,
    rolling_low,
    session_vwap,
    sma,
)
from app.models import Bias, MarketRegime, MarketRegimeResult, Signal, SignalLevel
from app.utils import now_ny

logger = logging.getLogger(__name__)

STRONG_THRESHOLD = 5
WATCH_THRESHOLD = 3

# ── Option structure suggestions ─────────────────────────────────────

SHORT_STRUCTURES = {
    "primary": "Bear Call Spread（熊市看涨价差）",
    "alternative": "Put Debit Spread（看跌借记价差）",
    "hint_primary": "可优先观察靠近昨日高点的卖出腿",
    "hint_alternative": "可优先考虑 ATM 或轻度 ITM 的看跌借记",
}

LONG_STRUCTURES = {
    "primary": "Bull Call Spread（牛市看涨价差）",
    "alternative": "Call Debit Spread（看涨借记价差）",
    "hint_primary": "可优先观察靠近昨日低点的买入腿",
    "hint_alternative": "可优先考虑 ATM 或轻度 ITM 的看涨借记",
}


class StrategyEngine:

    def evaluate_symbol(self, symbol: str, regime: MarketRegimeResult) -> Signal:
        upper = symbol.upper()
        if upper in settings.short_symbols:
            return self._short_setup(symbol, regime)
        elif upper in settings.long_symbols:
            return self._long_setup(symbol, regime)
        else:
            bias = self._auto_detect_bias(symbol)
            if bias == Bias.LONG:
                return self._long_setup(symbol, regime)
            return self._short_setup(symbol, regime)

    def evaluate_with_data(self, symbol: str, regime: MarketRegimeResult, daily: pd.DataFrame) -> Signal:
        """Evaluate using pre-sliced data (for backtesting — no intraday)."""
        upper = symbol.upper()
        if upper in settings.short_symbols:
            return self._short_setup(symbol, regime, daily=daily, intraday=pd.DataFrame())
        elif upper in settings.long_symbols:
            return self._long_setup(symbol, regime, daily=daily, intraday=pd.DataFrame())
        else:
            bias = self._auto_detect_bias_from_data(daily)
            if bias == Bias.LONG:
                return self._long_setup(symbol, regime, daily=daily, intraday=pd.DataFrame())
            return self._short_setup(symbol, regime, daily=daily, intraday=pd.DataFrame())

    def _auto_detect_bias(self, symbol: str) -> Bias:
        daily = get_daily(symbol, days=60)
        return self._auto_detect_bias_from_data(daily)

    @staticmethod
    def _auto_detect_bias_from_data(daily: pd.DataFrame) -> Bias:
        if daily.empty or len(daily) < 20:
            return Bias.SHORT
        close = daily["Close"]
        sma20 = float(close.rolling(20).mean().iloc[-1])
        current = float(close.iloc[-1])
        if current > sma20:
            return Bias.LONG
        return Bias.SHORT

    def _short_setup(
        self,
        symbol: str,
        regime: MarketRegimeResult,
        daily: pd.DataFrame | None = None,
        intraday: pd.DataFrame | None = None,
    ) -> Signal:
        """逢高做空 — USO / XOM / XLE."""
        if daily is None:
            daily = get_daily(symbol, days=60)
        if intraday is None:
            intraday = get_intraday(symbol)

        if daily.empty:
            return self._empty_signal(symbol, Bias.SHORT)

        score = 0
        reasons: list[str] = []
        close = daily["Close"]
        current_price = float(close.iloc[-1])

        # ── Regime filter ────────────────────────────────────────────
        if regime.regime == MarketRegime.RISK_ON:
            score -= 2
            reasons.append("大盘环境 risk_on，不利于做空 (-2)")
        elif regime.regime == MarketRegime.RISK_OFF:
            score += 1
            reasons.append("大盘环境 risk_off，有利于做空 (+1)")
        else:
            score += 1
            reasons.append("大盘环境 neutral，允许偏空 (+1)")

        # ── Price vs previous day high ───────────────────────────────
        pdh = prev_day_high(daily)
        if not math.isnan(pdh):
            proximity = abs(current_price - pdh) / pdh
            if proximity < 0.005:
                score += 2
                reasons.append(f"现价 ({current_price:.2f}) 接近昨日高点 ({pdh:.2f}) (+2)")
            elif proximity < 0.015:
                score += 1
                reasons.append(f"现价 ({current_price:.2f}) 靠近昨日高点 ({pdh:.2f}) (+1)")

        # ── Price vs SMA5 ────────────────────────────────────────────
        sma5 = sma(close, 5)
        sma10 = sma(close, 10)
        if pd.notna(sma5.iloc[-1]) and pd.notna(sma10.iloc[-1]):
            sma5_val = float(sma5.iloc[-1])
            sma10_val = float(sma10.iloc[-1])
            if sma5_val < sma10_val:
                score += 1
                reasons.append(f"5日均线 ({sma5_val:.2f}) 低于10日均线 ({sma10_val:.2f})，空头排列 (+1)")
            if current_price > sma5_val and abs(current_price - sma5_val) / sma5_val < 0.01:
                score += 1
                reasons.append(f"现价接近5日均线压力位 ({sma5_val:.2f}) (+1)")

        # ── Rolling 20-day high zone ─────────────────────────────────
        r_high = rolling_high(daily, 20)
        r_low = rolling_low(daily, 20)
        if pd.notna(r_high.iloc[-1]) and pd.notna(r_low.iloc[-1]):
            high_val = float(r_high.iloc[-1])
            low_val = float(r_low.iloc[-1])
            range_size = high_val - low_val
            if range_size > 0:
                position = (current_price - low_val) / range_size
                if position > 0.8:
                    score += 2
                    reasons.append(f"价格位于近20日高位区域 ({position:.0%}) (+2)")
                elif position > 0.6:
                    score += 1
                    reasons.append(f"价格位于近20日偏高区域 ({position:.0%}) (+1)")

        # ── Intraday VWAP ────────────────────────────────────────────
        trigger_price = current_price
        if not intraday.empty:
            vwap = session_vwap(intraday)
            if not vwap.empty and pd.notna(vwap.iloc[-1]):
                vwap_val = float(vwap.iloc[-1])
                if current_price < vwap_val:
                    score += 1
                    reasons.append(f"盘中价格 ({current_price:.2f}) 跌回 VWAP ({vwap_val:.2f}) 下方 (+1)")
                    trigger_price = vwap_val

        # ── ATR context ──────────────────────────────────────────────
        atr_series = atr(daily, 14)
        if pd.notna(atr_series.iloc[-1]):
            atr_val = float(atr_series.iloc[-1])
            reasons.append(f"ATR(14): {atr_val:.2f}")

        # ── Build signal ─────────────────────────────────────────────
        level = self._score_to_level(score)
        structures = SHORT_STRUCTURES

        action = ""
        if level == SignalLevel.STRONG:
            action = f"考虑建立 {structures['primary']}"
        elif level == SignalLevel.WATCH:
            action = "观察中，等待更多确认条件"

        return Signal(
            symbol=symbol,
            bias=Bias.SHORT,
            level=level,
            action=action,
            rationale=reasons,
            price=current_price,
            trigger_price=trigger_price,
            option_structure=structures["primary"] if level != SignalLevel.NONE else "",
            option_hint=structures["hint_primary"] if level == SignalLevel.STRONG else "",
            timestamp=now_ny(),
            score=score,
        )

    def _long_setup(
        self,
        symbol: str,
        regime: MarketRegimeResult,
        daily: pd.DataFrame | None = None,
        intraday: pd.DataFrame | None = None,
    ) -> Signal:
        """逢低做多 — CRM."""
        if daily is None:
            daily = get_daily(symbol, days=60)
        if intraday is None:
            intraday = get_intraday(symbol)

        if daily.empty:
            return self._empty_signal(symbol, Bias.LONG)

        score = 0
        reasons: list[str] = []
        close = daily["Close"]
        current_price = float(close.iloc[-1])

        # ── Regime filter ────────────────────────────────────────────
        if regime.regime == MarketRegime.RISK_OFF:
            score -= 2
            reasons.append("大盘环境 risk_off，不利于做多 (-2)")
        elif regime.regime == MarketRegime.RISK_ON:
            score += 1
            reasons.append("大盘环境 risk_on，有利于做多 (+1)")
        else:
            score += 1
            reasons.append("大盘环境 neutral，允许偏多 (+1)")

        # ── Price vs previous day low ────────────────────────────────
        pdl = prev_day_low(daily)
        if not math.isnan(pdl):
            proximity = abs(current_price - pdl) / pdl
            if proximity < 0.005:
                score += 2
                reasons.append(f"现价 ({current_price:.2f}) 接近昨日低点 ({pdl:.2f}) (+2)")
            elif proximity < 0.015:
                score += 1
                reasons.append(f"现价 ({current_price:.2f}) 靠近昨日低点 ({pdl:.2f}) (+1)")

        # ── Price vs SMA5 / SMA10 support ────────────────────────────
        sma5 = sma(close, 5)
        sma10 = sma(close, 10)
        if pd.notna(sma5.iloc[-1]) and pd.notna(sma10.iloc[-1]):
            sma5_val = float(sma5.iloc[-1])
            sma10_val = float(sma10.iloc[-1])
            if current_price < sma5_val and abs(current_price - sma5_val) / sma5_val < 0.01:
                score += 1
                reasons.append(f"现价接近5日均线支撑 ({sma5_val:.2f}) (+1)")
            if current_price < sma10_val and abs(current_price - sma10_val) / sma10_val < 0.015:
                score += 1
                reasons.append(f"现价靠近10日均线支撑 ({sma10_val:.2f}) (+1)")

        # ── Rolling 20-day low zone ──────────────────────────────────
        r_high = rolling_high(daily, 20)
        r_low = rolling_low(daily, 20)
        if pd.notna(r_high.iloc[-1]) and pd.notna(r_low.iloc[-1]):
            high_val = float(r_high.iloc[-1])
            low_val = float(r_low.iloc[-1])
            range_size = high_val - low_val
            if range_size > 0:
                position = (current_price - low_val) / range_size
                if position < 0.2:
                    score += 2
                    reasons.append(f"价格位于近20日低位区域 ({position:.0%}) (+2)")
                elif position < 0.4:
                    score += 1
                    reasons.append(f"价格位于近20日偏低区域 ({position:.0%}) (+1)")

        # ── Intraday VWAP ────────────────────────────────────────────
        trigger_price = current_price
        if not intraday.empty:
            vwap = session_vwap(intraday)
            if not vwap.empty and pd.notna(vwap.iloc[-1]):
                vwap_val = float(vwap.iloc[-1])
                if current_price > vwap_val:
                    score += 1
                    reasons.append(f"盘中重新站上 VWAP ({vwap_val:.2f}) (+1)")
                    trigger_price = vwap_val

        # ── Short-term stabilization ─────────────────────────────────
        if len(daily) >= 3:
            last3_low = daily["Low"].iloc[-3:].min()
            last3_close = close.iloc[-3:]
            if all(last3_close > last3_low * 0.995):
                score += 1
                reasons.append("近3日价格企稳，未再创新低 (+1)")

        # ── ATR context ──────────────────────────────────────────────
        atr_series = atr(daily, 14)
        if pd.notna(atr_series.iloc[-1]):
            atr_val = float(atr_series.iloc[-1])
            reasons.append(f"ATR(14): {atr_val:.2f}")

        # ── Build signal ─────────────────────────────────────────────
        level = self._score_to_level(score)
        structures = LONG_STRUCTURES

        action = ""
        if level == SignalLevel.STRONG:
            action = f"考虑建立 {structures['primary']}"
        elif level == SignalLevel.WATCH:
            action = "观察中，等待更多确认条件"

        return Signal(
            symbol=symbol,
            bias=Bias.LONG,
            level=level,
            action=action,
            rationale=reasons,
            price=current_price,
            trigger_price=trigger_price,
            option_structure=structures["primary"] if level != SignalLevel.NONE else "",
            option_hint=structures["hint_primary"] if level == SignalLevel.STRONG else "",
            timestamp=now_ny(),
            score=score,
        )

    @staticmethod
    def _score_to_level(score: int) -> SignalLevel:
        if score >= STRONG_THRESHOLD:
            return SignalLevel.STRONG
        elif score >= WATCH_THRESHOLD:
            return SignalLevel.WATCH
        return SignalLevel.NONE

    @staticmethod
    def _empty_signal(symbol: str, bias: Bias) -> Signal:
        return Signal(
            symbol=symbol,
            bias=bias,
            level=SignalLevel.NONE,
            action="数据不足，无法评估",
            rationale=["本地无该标的数据"],
            timestamp=now_ny(),
        )
