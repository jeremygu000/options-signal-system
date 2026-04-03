"""Backtester — bridges our signal system with optopsy for historical strategy evaluation.

Translates Signal objects into optopsy strategy executions and returns
simulation results with risk metrics.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import pandas as pd

import optopsy as op

from app.models import Bias, Signal, SignalLevel

logger = logging.getLogger(__name__)


class StrategyType(str, Enum):
    SHORT_CALL_SPREAD = "short_call_spread"
    LONG_PUT_SPREAD = "long_put_spread"
    SHORT_CALLS = "short_calls"
    SHORT_PUTS = "short_puts"
    LONG_CALLS = "long_calls"
    LONG_PUTS = "long_puts"
    LONG_CALL_SPREAD = "long_call_spread"
    SHORT_PUT_SPREAD = "short_put_spread"
    IRON_CONDOR = "iron_condor"
    STRADDLE = "straddle"


BIAS_TO_STRATEGIES: dict[Bias, list[StrategyType]] = {
    Bias.SHORT: [StrategyType.SHORT_CALL_SPREAD, StrategyType.LONG_PUT_SPREAD],
    Bias.LONG: [StrategyType.LONG_CALL_SPREAD, StrategyType.SHORT_PUT_SPREAD],
}

_STRATEGY_FUNCS: dict[StrategyType, Any] = {
    StrategyType.SHORT_CALL_SPREAD: op.short_call_spread,
    StrategyType.LONG_PUT_SPREAD: op.long_put_spread,
    StrategyType.SHORT_CALLS: op.short_calls,
    StrategyType.SHORT_PUTS: op.short_puts,
    StrategyType.LONG_CALLS: op.long_calls,
    StrategyType.LONG_PUTS: op.long_puts,
    StrategyType.LONG_CALL_SPREAD: op.long_call_spread,
    StrategyType.SHORT_PUT_SPREAD: op.short_put_spread,
    StrategyType.IRON_CONDOR: op.iron_condor,
    StrategyType.STRADDLE: op.long_straddles,
}


@dataclass(frozen=True)
class BacktestConfig:
    """Parameters for a single backtest run."""

    strategy_type: StrategyType
    max_entry_dte: int = 45
    exit_dte: int = 21
    leg1_delta: float = 0.30
    leg2_delta: float = 0.16
    capital: float = 100_000.0
    quantity: int = 1
    max_positions: int = 1
    multiplier: int = 100
    commission_per_contract: float = 0.65
    stop_loss: float | None = None
    take_profit: float | None = None


@dataclass
class BacktestResult:
    """Aggregated backtest output."""

    symbol: str
    strategy: str
    config: BacktestConfig
    total_trades: int = 0
    win_rate: float = 0.0
    mean_return: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    max_drawdown: float = 0.0
    profit_factor: float = 0.0
    calmar_ratio: float = 0.0
    final_equity: float = 0.0
    equity_curve: list[float] = field(default_factory=list)
    trade_log: list[dict[str, Any]] = field(default_factory=list)
    raw_summary: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


def signal_to_strategies(signal: Signal) -> list[StrategyType]:
    """Map a Signal to the appropriate optopsy strategy types based on bias."""
    if signal.level == SignalLevel.NONE:
        return []
    return BIAS_TO_STRATEGIES.get(signal.bias, [])


def run_backtest(
    options_data: pd.DataFrame,
    stock_data: pd.DataFrame,
    config: BacktestConfig,
    signal_dates: list[str] | None = None,
) -> BacktestResult:
    """Execute a single backtest using optopsy.

    Args:
        options_data: Options chain data in optopsy format.
        stock_data: Underlying OHLCV data with columns: underlying_symbol, quote_date.
        config: Backtest parameters.
        signal_dates: Optional list of entry dates (YYYY-MM-DD). If provided,
                     only these dates are used for entry.

    Returns:
        BacktestResult with metrics, equity curve, and trade log.
    """
    symbol = ""
    if not options_data.empty and "underlying_symbol" in options_data.columns:
        symbol = str(options_data["underlying_symbol"].iloc[0])

    result = BacktestResult(symbol=symbol, strategy=config.strategy_type.value, config=config)

    if options_data.empty:
        result.error = "No options data provided"
        return result

    strategy_func = _STRATEGY_FUNCS.get(config.strategy_type)
    if strategy_func is None:
        result.error = f"Unknown strategy: {config.strategy_type}"
        return result

    try:
        strategy_kwargs = _build_strategy_kwargs(config)

        entry_dates_df: pd.DataFrame | None = None
        if signal_dates and not stock_data.empty:
            signal_df = stock_data.copy()
            signal_df["signal"] = signal_df["quote_date"].dt.strftime("%Y-%m-%d").isin(signal_dates)
            sig_func = op.custom_signal(signal_df, flag_col="signal")
            entry_dates_df = op.signal_dates(stock_data, sig_func)

        sim_kwargs: dict[str, Any] = {
            "data": options_data,
            "strategy": strategy_func,
            "capital": config.capital,
            "quantity": config.quantity,
            "max_positions": config.max_positions,
            "multiplier": config.multiplier,
            **strategy_kwargs,
        }

        if entry_dates_df is not None:
            sim_kwargs["entry_dates"] = entry_dates_df

        sim_result = op.simulate(**sim_kwargs)

        result.total_trades = len(sim_result.trade_log) if hasattr(sim_result, "trade_log") else 0

        if hasattr(sim_result, "summary") and sim_result.summary:
            summary = sim_result.summary
            result.raw_summary = dict(summary) if isinstance(summary, dict) else {}

        if hasattr(sim_result, "trade_log") and not sim_result.trade_log.empty:
            log_df = sim_result.trade_log
            result.trade_log = [{str(k): v for k, v in row.items()} for row in log_df.head(200).to_dict("records")]

            if "pct_change" in log_df.columns:
                returns = log_df["pct_change"]
                result.mean_return = float(returns.mean())
                result.win_rate = float((returns > 0).mean())

                if returns.std() > 0:
                    result.sharpe_ratio = float(op.sharpe_ratio(returns))
                    result.sortino_ratio = float(op.sortino_ratio(returns))
                    result.profit_factor = float(op.profit_factor(returns))

                result.max_drawdown = float(op.max_drawdown_from_returns(returns))

        if hasattr(sim_result, "equity_curve"):
            curve = sim_result.equity_curve
            if isinstance(curve, pd.Series) and not curve.empty:
                result.equity_curve = [float(v) for v in curve.values[-500:]]
                result.final_equity = float(curve.iloc[-1])

    except Exception as exc:
        logger.exception("Backtest failed for %s with %s", symbol, config.strategy_type.value)
        result.error = str(exc)

    return result


def run_multi_strategy_backtest(
    options_data: pd.DataFrame,
    stock_data: pd.DataFrame,
    signal: Signal,
    base_config: BacktestConfig | None = None,
) -> list[BacktestResult]:
    """Run backtests for all strategies appropriate to a signal's bias.

    Args:
        options_data: Options chain data in optopsy format.
        stock_data: Underlying OHLCV data.
        signal: The signal whose bias determines which strategies to test.
        base_config: Base configuration; strategy_type will be overridden.

    Returns:
        List of BacktestResult, one per strategy.
    """
    strategies = signal_to_strategies(signal)
    if not strategies:
        return []

    results: list[BacktestResult] = []
    for strategy_type in strategies:
        cfg = BacktestConfig(
            strategy_type=strategy_type,
            max_entry_dte=base_config.max_entry_dte if base_config else 45,
            exit_dte=base_config.exit_dte if base_config else 21,
            leg1_delta=base_config.leg1_delta if base_config else 0.30,
            leg2_delta=base_config.leg2_delta if base_config else 0.16,
            capital=base_config.capital if base_config else 100_000.0,
            quantity=base_config.quantity if base_config else 1,
            max_positions=base_config.max_positions if base_config else 1,
            multiplier=base_config.multiplier if base_config else 100,
            commission_per_contract=base_config.commission_per_contract if base_config else 0.65,
            stop_loss=base_config.stop_loss if base_config else None,
            take_profit=base_config.take_profit if base_config else None,
        )
        result = run_backtest(options_data, stock_data, cfg)
        results.append(result)

    return results


def _build_strategy_kwargs(config: BacktestConfig) -> dict[str, Any]:
    """Translate BacktestConfig into optopsy strategy keyword arguments."""
    kwargs: dict[str, Any] = {
        "max_entry_dte": config.max_entry_dte,
        "exit_dte": config.exit_dte,
    }

    spread_strategies = {
        StrategyType.SHORT_CALL_SPREAD,
        StrategyType.LONG_PUT_SPREAD,
        StrategyType.LONG_CALL_SPREAD,
        StrategyType.SHORT_PUT_SPREAD,
    }
    if config.strategy_type in spread_strategies:
        kwargs["leg1_delta"] = op.TargetRange(
            target=config.leg1_delta,
            min=config.leg1_delta - 0.05,
            max=config.leg1_delta + 0.05,
        )
        kwargs["leg2_delta"] = op.TargetRange(
            target=config.leg2_delta,
            min=config.leg2_delta - 0.05,
            max=config.leg2_delta + 0.05,
        )
    elif config.strategy_type in {StrategyType.IRON_CONDOR}:
        kwargs["leg1_delta"] = op.TargetRange(target=0.30, min=0.25, max=0.35)
        kwargs["leg2_delta"] = op.TargetRange(target=0.16, min=0.11, max=0.21)
        kwargs["leg3_delta"] = op.TargetRange(target=0.30, min=0.25, max=0.35)
        kwargs["leg4_delta"] = op.TargetRange(target=0.16, min=0.11, max=0.21)
    else:
        kwargs["leg1_delta"] = op.TargetRange(
            target=config.leg1_delta,
            min=config.leg1_delta - 0.05,
            max=config.leg1_delta + 0.05,
        )

    commission = op.Commission(
        per_contract=config.commission_per_contract,
        per_share=0.0,
        base_fee=0.0,
        min_fee=0.0,
    )
    kwargs["commission"] = commission

    if config.stop_loss is not None:
        kwargs["stop_loss"] = config.stop_loss
    if config.take_profit is not None:
        kwargs["take_profit"] = config.take_profit

    return kwargs
