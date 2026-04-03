from __future__ import annotations

from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from app.models import Bias, MarketRegime, MarketRegimeResult, SignalLevel
from app.strategy_engine import StrategyEngine


def _make_daily(n: int, base: float = 78.0, trend: str = "flat") -> pd.DataFrame:
    dates = pd.bdate_range(end=pd.Timestamp.now(), periods=n + 5)[-n:]
    if trend == "up":
        closes = base + np.linspace(0, 10, n)
    elif trend == "down":
        closes = base - np.linspace(0, 10, n)
    else:
        closes = np.full(n, base)
    highs = closes + 1.0
    lows = closes - 1.0
    opens = closes - 0.3
    volumes = np.full(n, 3_000_000)
    return pd.DataFrame(
        {"Open": opens, "High": highs, "Low": lows, "Close": closes, "Volume": volumes},
        index=dates,
    )


def _make_intraday() -> pd.DataFrame:
    idx = pd.date_range("2024-01-02 09:30", periods=20, freq="15min")
    closes = np.linspace(78.0, 77.5, 20)
    return pd.DataFrame(
        {
            "Open": closes + 0.1,
            "High": closes + 0.5,
            "Low": closes - 0.5,
            "Close": closes,
            "Volume": np.full(20, 500_000),
        },
        index=idx,
    )


def _neutral_regime() -> MarketRegimeResult:
    return MarketRegimeResult(regime=MarketRegime.NEUTRAL, reasons=["test"])


def _risk_on_regime() -> MarketRegimeResult:
    return MarketRegimeResult(regime=MarketRegime.RISK_ON, reasons=["test"])


def _risk_off_regime() -> MarketRegimeResult:
    return MarketRegimeResult(regime=MarketRegime.RISK_OFF, reasons=["test"])


class TestShortSetup:
    @patch("app.strategy_engine.get_intraday")
    @patch("app.strategy_engine.get_daily")
    def test_short_with_neutral_regime(self, mock_daily, mock_intraday):
        mock_daily.return_value = _make_daily(30)
        mock_intraday.return_value = _make_intraday()

        engine = StrategyEngine()
        signal = engine.evaluate_symbol("USO", _neutral_regime())
        assert signal.bias == Bias.SHORT
        assert signal.symbol == "USO"
        assert signal.score >= 0

    @patch("app.strategy_engine.get_intraday")
    @patch("app.strategy_engine.get_daily")
    def test_short_penalised_in_risk_on(self, mock_daily, mock_intraday):
        mock_daily.return_value = _make_daily(30)
        mock_intraday.return_value = _make_intraday()

        engine = StrategyEngine()
        neutral_sig = engine.evaluate_symbol("USO", _neutral_regime())
        risk_on_sig = engine.evaluate_symbol("USO", _risk_on_regime())
        assert risk_on_sig.score < neutral_sig.score

    @patch("app.strategy_engine.get_intraday")
    @patch("app.strategy_engine.get_daily")
    def test_empty_daily_returns_none_signal(self, mock_daily, mock_intraday):
        mock_daily.return_value = pd.DataFrame()
        mock_intraday.return_value = pd.DataFrame()

        engine = StrategyEngine()
        signal = engine.evaluate_symbol("USO", _neutral_regime())
        assert signal.level == SignalLevel.NONE
        assert "数据不足" in signal.action


class TestLongSetup:
    @patch("app.strategy_engine.get_intraday")
    @patch("app.strategy_engine.get_daily")
    def test_long_with_neutral_regime(self, mock_daily, mock_intraday):
        mock_daily.return_value = _make_daily(30, base=250.0)
        mock_intraday.return_value = pd.DataFrame()

        engine = StrategyEngine()
        signal = engine.evaluate_symbol("CRM", _neutral_regime())
        assert signal.bias == Bias.LONG
        assert signal.symbol == "CRM"

    @patch("app.strategy_engine.get_intraday")
    @patch("app.strategy_engine.get_daily")
    def test_long_penalised_in_risk_off(self, mock_daily, mock_intraday):
        mock_daily.return_value = _make_daily(30, base=250.0)
        mock_intraday.return_value = pd.DataFrame()

        engine = StrategyEngine()
        neutral_sig = engine.evaluate_symbol("CRM", _neutral_regime())
        risk_off_sig = engine.evaluate_symbol("CRM", _risk_off_regime())
        assert risk_off_sig.score < neutral_sig.score


class TestScoring:
    def test_score_thresholds(self):
        engine = StrategyEngine()
        assert engine._score_to_level(5) == SignalLevel.STRONG
        assert engine._score_to_level(6) == SignalLevel.STRONG
        assert engine._score_to_level(3) == SignalLevel.WATCH
        assert engine._score_to_level(4) == SignalLevel.WATCH
        assert engine._score_to_level(2) == SignalLevel.NONE
        assert engine._score_to_level(0) == SignalLevel.NONE
        assert engine._score_to_level(-1) == SignalLevel.NONE
