"""Signal backtesting engine — replay signals historically and evaluate outcomes.

Event-driven day-by-day loop that slices data as-of each date to prevent
lookahead bias. Evaluates forward returns at multiple horizons.
"""

from __future__ import annotations

import logging
import math
from datetime import date, timedelta

import pandas as pd

from app.data_provider import get_daily
from app.market_regime import MarketRegimeEngine
from app.models import (
    Bias,
    HorizonBreakdown,
    MarketRegimeResult,
    RegimeBreakdown,
    SignalBacktestMetrics,
    SignalBacktestResponse,
    SignalLevel,
    SignalOutcome,
    WalkForwardResponse,
    WalkForwardWindow,
)
from app.strategy_engine import StrategyEngine

logger = logging.getLogger(__name__)

_DEFAULT_LOOKBACK = 60
_QQQ = "QQQ"
_VIX = "^VIX"


def _get_daily_as_of(full_daily: pd.DataFrame, as_of: date, lookback: int = _DEFAULT_LOOKBACK) -> pd.DataFrame:
    ts = pd.Timestamp(as_of)
    sliced = full_daily.loc[:ts]
    if lookback and len(sliced) > lookback:
        sliced = sliced.iloc[-lookback:]
    return sliced


def _forward_return(full_daily: pd.DataFrame, signal_date: date, horizon: int) -> float | None:
    ts = pd.Timestamp(signal_date)
    future = full_daily.loc[ts:]
    if len(future) < horizon + 1:
        return None
    entry_price = float(future.iloc[0]["Close"])
    exit_price = float(future.iloc[horizon]["Close"])
    if entry_price == 0:
        return None
    return (exit_price - entry_price) / entry_price


def _is_hit(ret: float, bias_str: str) -> bool:
    if bias_str == Bias.LONG.value:
        return ret > 0
    return ret < 0


def run_signal_backtest(
    symbol: str,
    start_date: date | None = None,
    end_date: date | None = None,
    horizons: list[int] | None = None,
) -> SignalBacktestResponse:
    if horizons is None:
        horizons = [1, 3, 5, 10, 20]

    today = date.today()
    if end_date is None:
        end_date = today
    if start_date is None:
        start_date = end_date - timedelta(days=365)

    full_daily = get_daily(symbol)
    qqq_daily = get_daily(_QQQ)
    vix_daily = get_daily(_VIX)

    if full_daily.empty:
        return SignalBacktestResponse(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            error=f"No Parquet data for {symbol}",
        )

    regime_engine = MarketRegimeEngine()
    strategy_engine = StrategyEngine()

    start_ts = pd.Timestamp(start_date)
    end_ts = pd.Timestamp(end_date)
    mask = (full_daily.index >= start_ts) & (full_daily.index <= end_ts)
    trading_dates = full_daily.index[mask]
    if trading_dates.empty:
        return SignalBacktestResponse(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            error=f"No trading data for {symbol} in [{start_date}, {end_date}]",
        )

    outcomes: list[SignalOutcome] = []
    equity = 1.0
    equity_curve: list[float] = [1.0]
    peak = 1.0
    max_dd = 0.0

    for ts in trading_dates:
        current_date = ts.date() if hasattr(ts, "date") else ts

        sym_slice = _get_daily_as_of(full_daily, current_date)
        qqq_slice = _get_daily_as_of(qqq_daily, current_date)
        vix_slice = _get_daily_as_of(vix_daily, current_date)

        if len(sym_slice) < 20 or qqq_slice.empty or vix_slice.empty:
            continue

        regime = regime_engine.evaluate_with_data(qqq_slice, vix_slice)
        signal = strategy_engine.evaluate_with_data(symbol, regime, sym_slice)

        if signal.level == SignalLevel.NONE:
            continue

        returns: dict[str, float] = {}
        hit: dict[str, bool] = {}
        for h in horizons:
            key = f"{h}d"
            ret = _forward_return(full_daily, current_date, h)
            if ret is not None:
                returns[key] = round(ret, 6)
                hit[key] = _is_hit(ret, signal.bias.value)

        outcomes.append(
            SignalOutcome(
                date=current_date,
                signal_level=signal.level.value,
                bias=signal.bias.value,
                score=signal.score,
                price=signal.price,
                returns=returns,
                hit=hit,
            )
        )

        default_h = "5d"
        if default_h in returns:
            equity *= 1 + returns[default_h]
        equity_curve.append(round(equity, 6))
        if equity > peak:
            peak = equity
        dd = (peak - equity) / peak if peak > 0 else 0.0
        if dd > max_dd:
            max_dd = dd

    metrics = _compute_metrics(outcomes, horizons, max_dd, equity_curve)

    return SignalBacktestResponse(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        metrics=metrics,
        outcomes=outcomes,
        equity_curve=equity_curve,
    )


def _compute_metrics(
    outcomes: list[SignalOutcome],
    horizons: list[int],
    max_dd: float,
    equity_curve: list[float],
) -> SignalBacktestMetrics:
    total = len(outcomes)
    if total == 0:
        return SignalBacktestMetrics()

    strong = [o for o in outcomes if o.signal_level == SignalLevel.STRONG.value]
    watch = [o for o in outcomes if o.signal_level == SignalLevel.WATCH.value]

    default_h = "5d"
    all_returns = [o.returns.get(default_h, 0.0) for o in outcomes if default_h in o.returns]
    all_hits = [o.hit.get(default_h, False) for o in outcomes if default_h in o.hit]

    overall_hit_rate = sum(all_hits) / len(all_hits) if all_hits else 0.0
    avg_ret = sum(all_returns) / len(all_returns) if all_returns else 0.0

    gains = [r for r in all_returns if r > 0]
    losses = [r for r in all_returns if r < 0]
    total_gain = sum(gains) if gains else 0.0
    total_loss = abs(sum(losses)) if losses else 0.0
    profit_factor = total_gain / total_loss if total_loss > 0 else float("inf") if total_gain > 0 else 0.0

    sharpe = 0.0
    if len(all_returns) > 1:
        mean_r = sum(all_returns) / len(all_returns)
        var = sum((r - mean_r) ** 2 for r in all_returns) / (len(all_returns) - 1)
        std = math.sqrt(var) if var > 0 else 0.0
        if std > 0:
            sharpe = round((mean_r / std) * math.sqrt(252), 4)

    by_horizon: list[HorizonBreakdown] = []
    for h in horizons:
        key = f"{h}d"
        h_outcomes = [o for o in outcomes if key in o.hit]
        h_hits = sum(1 for o in h_outcomes if o.hit[key])
        h_strong = [o for o in h_outcomes if o.signal_level == SignalLevel.STRONG.value]
        h_strong_hits = sum(1 for o in h_strong if o.hit.get(key, False))
        h_watch = [o for o in h_outcomes if o.signal_level == SignalLevel.WATCH.value]
        h_watch_hits = sum(1 for o in h_watch if o.hit.get(key, False))
        h_returns = [o.returns[key] for o in h_outcomes if key in o.returns]

        by_horizon.append(
            HorizonBreakdown(
                horizon=key,
                total_signals=len(h_outcomes),
                hits=h_hits,
                hit_rate=round(h_hits / len(h_outcomes), 4) if h_outcomes else 0.0,
                avg_return=round(sum(h_returns) / len(h_returns), 6) if h_returns else 0.0,
                strong_signals=len(h_strong),
                strong_hits=h_strong_hits,
                strong_hit_rate=round(h_strong_hits / len(h_strong), 4) if h_strong else 0.0,
                watch_signals=len(h_watch),
                watch_hits=h_watch_hits,
                watch_hit_rate=round(h_watch_hits / len(h_watch), 4) if h_watch else 0.0,
            )
        )

    regime_groups: dict[str, list[SignalOutcome]] = {}
    for o in outcomes:
        regime_key = "unknown"
        if default_h in o.hit:
            regime_key = _infer_regime_label(o)
        regime_groups.setdefault(regime_key, []).append(o)

    by_regime: list[RegimeBreakdown] = []
    for regime_label, group in sorted(regime_groups.items()):
        r_hits = [o.hit.get(default_h, False) for o in group if default_h in o.hit]
        r_returns = [o.returns.get(default_h, 0.0) for o in group if default_h in o.returns]
        by_regime.append(
            RegimeBreakdown(
                regime=regime_label,
                total_signals=len(group),
                hit_rate=round(sum(r_hits) / len(r_hits), 4) if r_hits else 0.0,
                avg_return=round(sum(r_returns) / len(r_returns), 6) if r_returns else 0.0,
            )
        )

    return SignalBacktestMetrics(
        total_days=total,
        signal_days=total,
        strong_days=len(strong),
        watch_days=len(watch),
        none_days=0,
        overall_hit_rate=round(overall_hit_rate, 4),
        avg_return=round(avg_ret, 6),
        profit_factor=round(profit_factor, 4) if not math.isinf(profit_factor) else 999.0,
        max_drawdown=round(max_dd, 4),
        sharpe=sharpe,
        by_horizon=by_horizon,
        by_regime=by_regime,
    )


def _infer_regime_label(outcome: SignalOutcome) -> str:
    if outcome.score >= 5:
        return "high_conviction"
    elif outcome.score >= 3:
        return "moderate_conviction"
    return "low_conviction"


def run_walk_forward(
    symbol: str,
    train_days: int = 252,
    test_days: int = 63,
    step_days: int = 21,
    horizon: int = 5,
) -> WalkForwardResponse:
    full_daily = get_daily(symbol)
    qqq_daily = get_daily(_QQQ)
    vix_daily = get_daily(_VIX)

    if full_daily.empty:
        return WalkForwardResponse(symbol=symbol, error=f"No Parquet data for {symbol}")

    all_dates = full_daily.index
    min_required = train_days + test_days
    if len(all_dates) < min_required:
        return WalkForwardResponse(
            symbol=symbol,
            error=f"Insufficient data: need {min_required} days, have {len(all_dates)}",
        )

    regime_engine = MarketRegimeEngine()
    strategy_engine = StrategyEngine()

    windows: list[WalkForwardWindow] = []
    start_idx = 0

    while start_idx + train_days + test_days <= len(all_dates):
        train_slice = all_dates[start_idx : start_idx + train_days]
        test_start_idx = start_idx + train_days
        test_end_idx = min(test_start_idx + test_days, len(all_dates))
        test_slice = all_dates[test_start_idx:test_end_idx]

        if len(test_slice) == 0:
            break

        is_hits: list[bool] = []
        for ts in train_slice:
            d = ts.date() if hasattr(ts, "date") else ts
            sym_s = _get_daily_as_of(full_daily, d)
            qqq_s = _get_daily_as_of(qqq_daily, d)
            vix_s = _get_daily_as_of(vix_daily, d)
            if len(sym_s) < 20 or qqq_s.empty or vix_s.empty:
                continue
            regime = regime_engine.evaluate_with_data(qqq_s, vix_s)
            signal = strategy_engine.evaluate_with_data(symbol, regime, sym_s)
            if signal.level == SignalLevel.NONE:
                continue
            ret = _forward_return(full_daily, d, horizon)
            if ret is not None:
                is_hits.append(_is_hit(ret, signal.bias.value))

        oos_hits: list[bool] = []
        oos_returns: list[float] = []
        for ts in test_slice:
            d = ts.date() if hasattr(ts, "date") else ts
            sym_s = _get_daily_as_of(full_daily, d)
            qqq_s = _get_daily_as_of(qqq_daily, d)
            vix_s = _get_daily_as_of(vix_daily, d)
            if len(sym_s) < 20 or qqq_s.empty or vix_s.empty:
                continue
            regime = regime_engine.evaluate_with_data(qqq_s, vix_s)
            signal = strategy_engine.evaluate_with_data(symbol, regime, sym_s)
            if signal.level == SignalLevel.NONE:
                continue
            ret = _forward_return(full_daily, d, horizon)
            if ret is not None:
                oos_hits.append(_is_hit(ret, signal.bias.value))
                oos_returns.append(ret)

        is_hr = sum(is_hits) / len(is_hits) if is_hits else 0.0
        oos_hr = sum(oos_hits) / len(oos_hits) if oos_hits else 0.0
        oos_ret = sum(oos_returns) / len(oos_returns) if oos_returns else 0.0

        train_start_d = train_slice[0].date() if hasattr(train_slice[0], "date") else train_slice[0]
        train_end_d = train_slice[-1].date() if hasattr(train_slice[-1], "date") else train_slice[-1]
        test_start_d = test_slice[0].date() if hasattr(test_slice[0], "date") else test_slice[0]
        test_end_d = test_slice[-1].date() if hasattr(test_slice[-1], "date") else test_slice[-1]

        windows.append(
            WalkForwardWindow(
                train_start=train_start_d,
                train_end=train_end_d,
                test_start=test_start_d,
                test_end=test_end_d,
                in_sample_hit_rate=round(is_hr, 4),
                out_of_sample_hit_rate=round(oos_hr, 4),
                out_of_sample_return=round(oos_ret, 6),
            )
        )

        start_idx += step_days

    if not windows:
        return WalkForwardResponse(symbol=symbol, error="No valid walk-forward windows")

    avg_oos_hr = sum(w.out_of_sample_hit_rate for w in windows) / len(windows)
    avg_oos_ret = sum(w.out_of_sample_return for w in windows) / len(windows)
    avg_is_hr = sum(w.in_sample_hit_rate for w in windows) / len(windows)
    stability = avg_oos_hr / avg_is_hr if avg_is_hr > 0 else 0.0

    return WalkForwardResponse(
        symbol=symbol,
        windows=windows,
        avg_oos_hit_rate=round(avg_oos_hr, 4),
        avg_oos_return=round(avg_oos_ret, 6),
        stability_ratio=round(stability, 4),
    )
