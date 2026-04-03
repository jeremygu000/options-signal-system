"""Market regime engine — 判断当前大盘环境 (risk_on / neutral / risk_off)。

Rules are transparent and score-based. Each condition adds or subtracts points.
Final regime is determined by total score thresholds.
"""

from __future__ import annotations

import logging
from datetime import datetime

import pandas as pd

from app.data_provider import get_daily
from app.indicators import sma
from app.models import MarketRegime, MarketRegimeResult
from app.utils import now_ny

logger = logging.getLogger(__name__)

RISK_ON_THRESHOLD = 3
RISK_OFF_THRESHOLD = -3


class MarketRegimeEngine:

    def __init__(self, qqq_symbol: str = "QQQ", vix_symbol: str = "^VIX") -> None:
        self._qqq_symbol = qqq_symbol
        self._vix_symbol = vix_symbol

    def evaluate(self) -> MarketRegimeResult:
        qqq_daily = get_daily(self._qqq_symbol, days=60)
        vix_daily = get_daily(self._vix_symbol, days=60)

        if qqq_daily.empty or vix_daily.empty:
            logger.error("Missing data for regime evaluation (QQQ=%d, VIX=%d rows)", len(qqq_daily), len(vix_daily))
            return MarketRegimeResult(
                regime=MarketRegime.NEUTRAL,
                reasons=["数据不足，默认 neutral"],
                qqq_price=0.0,
                vix_price=0.0,
            )

        score = 0
        reasons: list[str] = []

        qqq_close = qqq_daily["Close"]
        qqq_price = float(qqq_close.iloc[-1])
        vix_close = vix_daily["Close"]
        vix_price = float(vix_close.iloc[-1])

        # ── QQQ conditions ───────────────────────────────────────────

        # 1) QQQ 连续3天收阳
        if len(qqq_daily) >= 4:
            last3_up = all(qqq_close.iloc[-(i + 1)] > qqq_daily["Open"].iloc[-(i + 1)] for i in range(3))
            if last3_up:
                score += 2
                reasons.append("QQQ 连续3天收阳 (+2)")
            else:
                last3_down = all(qqq_close.iloc[-(i + 1)] < qqq_daily["Open"].iloc[-(i + 1)] for i in range(3))
                if last3_down:
                    score -= 2
                    reasons.append("QQQ 连续3天收阴 (-2)")

        # 2) QQQ vs 5日均线
        qqq_sma5 = sma(qqq_close, 5)
        if not qqq_sma5.empty and pd.notna(qqq_sma5.iloc[-1]):
            sma5_val = float(qqq_sma5.iloc[-1])
            if qqq_price > sma5_val:
                score += 1
                reasons.append(f"QQQ ({qqq_price:.2f}) 站上5日均线 ({sma5_val:.2f}) (+1)")
            else:
                score -= 1
                reasons.append(f"QQQ ({qqq_price:.2f}) 跌破5日均线 ({sma5_val:.2f}) (-1)")

        # 3) QQQ vs 上周高点
        if len(qqq_daily) >= 10:
            last_week = qqq_daily.iloc[-10:-5]
            if not last_week.empty:
                prev_week_high = float(last_week["High"].max())
                if qqq_price > prev_week_high:
                    score += 1
                    reasons.append(f"QQQ 突破上周高点 ({prev_week_high:.2f}) (+1)")
                prev_week_low = float(last_week["Low"].min())
                if qqq_price < prev_week_low:
                    score -= 1
                    reasons.append(f"QQQ 跌破上周低点 ({prev_week_low:.2f}) (-1)")

        # ── VIX conditions ───────────────────────────────────────────

        # 4) VIX 绝对水平
        if vix_price < 15:
            score += 1
            reasons.append(f"VIX ({vix_price:.2f}) 低于 15，市场平静 (+1)")
        elif vix_price > 25:
            score -= 2
            reasons.append(f"VIX ({vix_price:.2f}) 高于 25，市场恐慌 (-2)")
        elif vix_price > 20:
            score -= 1
            reasons.append(f"VIX ({vix_price:.2f}) 高于 20，市场紧张 (-1)")

        # 5) VIX vs 上周低点
        if len(vix_daily) >= 10:
            vix_last_week = vix_daily.iloc[-10:-5]
            if not vix_last_week.empty:
                vix_prev_week_low = float(vix_last_week["Low"].min())
                if vix_price < vix_prev_week_low:
                    score += 1
                    reasons.append(f"VIX 跌破上周低点 ({vix_prev_week_low:.2f})，恐慌消退 (+1)")

        # ── Determine regime ─────────────────────────────────────────

        if score >= RISK_ON_THRESHOLD:
            regime = MarketRegime.RISK_ON
        elif score <= RISK_OFF_THRESHOLD:
            regime = MarketRegime.RISK_OFF
        else:
            regime = MarketRegime.NEUTRAL

        reasons.append(f"综合评分: {score} → {regime.value}")

        logger.info("Market regime: %s (score=%d)", regime.value, score)
        return MarketRegimeResult(
            regime=regime,
            reasons=reasons,
            qqq_price=qqq_price,
            vix_price=vix_price,
            timestamp=now_ny(),
        )
