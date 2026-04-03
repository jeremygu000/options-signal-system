from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from app.backtester import (
    BacktestConfig,
    BacktestResult,
    StrategyType,
    _build_strategy_kwargs,
    run_backtest,
    run_multi_strategy_backtest,
    signal_to_strategies,
)
from app.models import Bias, Signal, SignalLevel


def _make_optopsy_data(symbol: str = "USO", n_strikes: int = 5) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for option_type in ["c", "p"]:
        for i in range(n_strikes):
            strike = 50.0 + i * 2
            rows.append(
                {
                    "underlying_symbol": symbol,
                    "option_type": option_type,
                    "expiration": pd.Timestamp("2025-05-16"),
                    "quote_date": pd.Timestamp("2025-04-04"),
                    "strike": strike,
                    "bid": max(0.1, 2.0 - i * 0.3),
                    "ask": max(0.2, 2.2 - i * 0.3),
                    "delta": (0.65 if i < 2 else 0.30) if option_type == "c" else (-0.65 if i >= 3 else -0.30),
                    "volume": 100,
                    "open_interest": 500,
                    "implied_volatility": 0.35,
                }
            )
    return pd.DataFrame(rows)


def _make_stock_data(symbol: str = "USO", n_days: int = 60) -> pd.DataFrame:
    dates = pd.bdate_range(end="2025-04-04", periods=n_days)
    return pd.DataFrame(
        {
            "underlying_symbol": symbol,
            "quote_date": dates,
            "close": [50.0 + i * 0.1 for i in range(n_days)],
        }
    )


def _make_signal(bias: Bias = Bias.SHORT, level: SignalLevel = SignalLevel.STRONG) -> Signal:
    return Signal(
        symbol="USO",
        bias=bias,
        level=level,
        action="test action",
        rationale=["test reason"],
        price=52.0,
        score=6,
    )


class TestSignalToStrategies:
    def test_short_bias_returns_short_strategies(self) -> None:
        signal = _make_signal(Bias.SHORT, SignalLevel.STRONG)
        strategies = signal_to_strategies(signal)
        assert StrategyType.SHORT_CALL_SPREAD in strategies
        assert StrategyType.LONG_PUT_SPREAD in strategies

    def test_long_bias_returns_long_strategies(self) -> None:
        signal = _make_signal(Bias.LONG, SignalLevel.WATCH)
        strategies = signal_to_strategies(signal)
        assert StrategyType.LONG_CALL_SPREAD in strategies
        assert StrategyType.SHORT_PUT_SPREAD in strategies

    def test_none_level_returns_empty(self) -> None:
        signal = _make_signal(Bias.SHORT, SignalLevel.NONE)
        assert signal_to_strategies(signal) == []


class TestBuildStrategyKwargs:
    def test_spread_strategy_has_two_legs(self) -> None:
        config = BacktestConfig(strategy_type=StrategyType.SHORT_CALL_SPREAD)
        kwargs = _build_strategy_kwargs(config)
        assert "leg1_delta" in kwargs
        assert "leg2_delta" in kwargs
        assert "commission" in kwargs

    def test_single_leg_strategy(self) -> None:
        config = BacktestConfig(strategy_type=StrategyType.SHORT_CALLS)
        kwargs = _build_strategy_kwargs(config)
        assert "leg1_delta" in kwargs
        assert "leg2_delta" not in kwargs

    def test_iron_condor_has_four_legs(self) -> None:
        config = BacktestConfig(strategy_type=StrategyType.IRON_CONDOR)
        kwargs = _build_strategy_kwargs(config)
        assert "leg1_delta" in kwargs
        assert "leg2_delta" in kwargs
        assert "leg3_delta" in kwargs
        assert "leg4_delta" in kwargs

    def test_stop_loss_included_when_set(self) -> None:
        config = BacktestConfig(strategy_type=StrategyType.SHORT_CALLS, stop_loss=0.5)
        kwargs = _build_strategy_kwargs(config)
        assert kwargs["stop_loss"] == 0.5

    def test_stop_loss_excluded_when_none(self) -> None:
        config = BacktestConfig(strategy_type=StrategyType.SHORT_CALLS)
        kwargs = _build_strategy_kwargs(config)
        assert "stop_loss" not in kwargs


class TestRunBacktest:
    def test_empty_data_returns_error(self) -> None:
        config = BacktestConfig(strategy_type=StrategyType.SHORT_CALL_SPREAD)
        result = run_backtest(pd.DataFrame(), pd.DataFrame(), config)
        assert result.error == "No options data provided"

    def test_unknown_strategy_returns_error(self) -> None:
        options = _make_optopsy_data()
        config = BacktestConfig(strategy_type=StrategyType.SHORT_CALL_SPREAD)
        with patch.dict("app.backtester._STRATEGY_FUNCS", {}, clear=True):
            result = run_backtest(options, pd.DataFrame(), config)
        assert result.error is not None
        assert "Unknown strategy" in result.error

    @patch("app.backtester.op.simulate")
    def test_successful_backtest(self, mock_simulate: MagicMock) -> None:
        mock_sim_result = MagicMock()
        mock_sim_result.summary = {"total_trades": 10, "win_rate": 0.6}
        trade_log = pd.DataFrame({"pct_change": [0.05, -0.02, 0.08, -0.01, 0.03]})
        mock_sim_result.trade_log = trade_log
        equity = pd.Series([100000, 100500, 100300, 100800, 100700, 101000])
        mock_sim_result.equity_curve = equity
        mock_simulate.return_value = mock_sim_result

        options = _make_optopsy_data()
        config = BacktestConfig(strategy_type=StrategyType.SHORT_CALL_SPREAD)
        result = run_backtest(options, pd.DataFrame(), config)

        assert result.error is None
        assert result.symbol == "USO"
        assert result.total_trades == 5
        assert result.final_equity == 101000.0
        assert len(result.equity_curve) == 6

    @patch("app.backtester.op.simulate")
    def test_backtest_exception_captured(self, mock_simulate: MagicMock) -> None:
        mock_simulate.side_effect = RuntimeError("optopsy internal error")
        options = _make_optopsy_data()
        config = BacktestConfig(strategy_type=StrategyType.SHORT_CALL_SPREAD)
        result = run_backtest(options, pd.DataFrame(), config)

        assert result.error is not None
        assert "optopsy internal error" in result.error


class TestRunMultiStrategyBacktest:
    @patch("app.backtester.run_backtest")
    def test_short_signal_runs_two_strategies(self, mock_bt: MagicMock) -> None:
        mock_bt.return_value = BacktestResult(
            symbol="USO",
            strategy="test",
            config=BacktestConfig(strategy_type=StrategyType.SHORT_CALL_SPREAD),
        )

        signal = _make_signal(Bias.SHORT, SignalLevel.STRONG)
        results = run_multi_strategy_backtest(_make_optopsy_data(), _make_stock_data(), signal)

        assert len(results) == 2
        assert mock_bt.call_count == 2

    def test_none_signal_returns_empty(self) -> None:
        signal = _make_signal(Bias.SHORT, SignalLevel.NONE)
        results = run_multi_strategy_backtest(_make_optopsy_data(), _make_stock_data(), signal)
        assert results == []

    @patch("app.backtester.run_backtest")
    def test_long_signal_runs_long_strategies(self, mock_bt: MagicMock) -> None:
        mock_bt.return_value = BacktestResult(
            symbol="CRM",
            strategy="test",
            config=BacktestConfig(strategy_type=StrategyType.LONG_CALL_SPREAD),
        )

        signal = _make_signal(Bias.LONG, SignalLevel.WATCH)
        results = run_multi_strategy_backtest(_make_optopsy_data("CRM"), _make_stock_data("CRM"), signal)

        assert len(results) == 2
