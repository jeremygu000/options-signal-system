from __future__ import annotations

from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from app.models import MarketRegime


def _make_daily(n: int, trend: str = "flat") -> pd.DataFrame:
    dates = pd.bdate_range(end=pd.Timestamp.now(), periods=n + 5)[-n:]
    base = 450.0
    if trend == "up":
        closes = base + np.linspace(0, 20, n)
        opens = closes - 1.5
    elif trend == "down":
        closes = base - np.linspace(0, 20, n)
        opens = closes + 1.5
    else:
        closes = np.full(n, base)
        opens = closes - 0.5
    highs = np.maximum(opens, closes) + 1.0
    lows = np.minimum(opens, closes) - 1.0
    volumes = np.full(n, 5_000_000)
    return pd.DataFrame(
        {"Open": opens, "High": highs, "Low": lows, "Close": closes, "Volume": volumes},
        index=dates,
    )


def _make_vix(n: int, level: float = 18.0) -> pd.DataFrame:
    dates = pd.bdate_range(end=pd.Timestamp.now(), periods=n + 5)[-n:]
    closes = np.full(n, level)
    highs = closes + 1.0
    lows = closes - 1.0
    opens = closes
    volumes = np.full(n, 1_000_000)
    return pd.DataFrame(
        {"Open": opens, "High": highs, "Low": lows, "Close": closes, "Volume": volumes},
        index=dates,
    )


class TestMarketRegime:
    @patch("app.market_regime.get_daily")
    def test_risk_on_with_uptrend_and_low_vix(self, mock_get_daily):
        def side_effect(symbol, days=60):
            if "VIX" in symbol.upper() or "VIX" in symbol:
                return _make_vix(30, level=13.0)
            return _make_daily(30, trend="up")

        mock_get_daily.side_effect = side_effect

        from app.market_regime import MarketRegimeEngine

        engine = MarketRegimeEngine()
        result = engine.evaluate()
        assert result.regime == MarketRegime.RISK_ON

    @patch("app.market_regime.get_daily")
    def test_risk_off_with_downtrend_and_high_vix(self, mock_get_daily):
        def side_effect(symbol, days=60):
            if "VIX" in symbol.upper() or "VIX" in symbol:
                return _make_vix(30, level=28.0)
            return _make_daily(30, trend="down")

        mock_get_daily.side_effect = side_effect

        from app.market_regime import MarketRegimeEngine

        engine = MarketRegimeEngine()
        result = engine.evaluate()
        assert result.regime == MarketRegime.RISK_OFF

    @patch("app.market_regime.get_daily")
    def test_neutral_with_flat_market(self, mock_get_daily):
        def side_effect(symbol, days=60):
            if "VIX" in symbol.upper() or "VIX" in symbol:
                return _make_vix(30, level=18.0)
            return _make_daily(30, trend="flat")

        mock_get_daily.side_effect = side_effect

        from app.market_regime import MarketRegimeEngine

        engine = MarketRegimeEngine()
        result = engine.evaluate()
        assert result.regime == MarketRegime.NEUTRAL

    @patch("app.market_regime.get_daily")
    def test_empty_data_returns_neutral(self, mock_get_daily):
        mock_get_daily.return_value = pd.DataFrame()

        from app.market_regime import MarketRegimeEngine

        engine = MarketRegimeEngine()
        result = engine.evaluate()
        assert result.regime == MarketRegime.NEUTRAL
        assert "数据不足" in result.reasons[0]

    @patch("app.market_regime.get_daily")
    def test_reasons_are_populated(self, mock_get_daily):
        def side_effect(symbol, days=60):
            if "VIX" in symbol.upper() or "VIX" in symbol:
                return _make_vix(30, level=18.0)
            return _make_daily(30, trend="up")

        mock_get_daily.side_effect = side_effect

        from app.market_regime import MarketRegimeEngine

        engine = MarketRegimeEngine()
        result = engine.evaluate()
        assert len(result.reasons) > 0
        assert any("综合评分" in r for r in result.reasons)
