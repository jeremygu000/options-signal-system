"""Multi-leg options strategy analyser.

Supports common multi-leg strategies (spreads, straddles, strangles,
iron condors, iron butterflies, custom combos up to 4 legs).

Provides:
    - ``analyze_multi_leg()``: Given legs + spot price, returns P&L
      characteristics, breakeven points, aggregated Greeks, and a P&L
      curve for charting.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from app.greeks import calculate_greeks, GreeksResult

# ── Data structures ──────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class OptionLeg:
    """A single leg of a multi-leg strategy."""

    option_type: str  # "c" or "p"
    action: str  # "buy" or "sell"
    strike: float
    expiration: str  # ISO date string, e.g. "2025-06-20"
    quantity: int  # number of contracts (always positive)
    premium: float  # per-share mid price (bid+ask)/2
    iv: float = 0.30  # implied volatility for Greeks calc


@dataclass(frozen=True, slots=True)
class PnLPoint:
    """Single point on the P&L-at-expiration curve."""

    price: float
    pnl: float


@dataclass(frozen=True, slots=True)
class AggregatedGreeks:
    """Net position Greeks across all legs."""

    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0
    vega: float = 0.0
    rho: float = 0.0


@dataclass(slots=True)
class MultiLegResult:
    """Full analysis result for a multi-leg strategy."""

    net_debit_credit: float = 0.0  # positive = debit, negative = credit
    max_profit: float = 0.0
    max_loss: float = 0.0
    breakeven_points: list[float] = field(default_factory=list)
    greeks: AggregatedGreeks = field(default_factory=AggregatedGreeks)
    pnl_curve: list[PnLPoint] = field(default_factory=list)


# ── Helpers ──────────────────────────────────────────────────────────

_RISK_FREE_RATE = 0.05


def _leg_direction(leg: OptionLeg) -> int:
    """Return +1 for buy, -1 for sell."""
    return 1 if leg.action == "buy" else -1


def _leg_payoff_at_expiration(leg: OptionLeg, underlying_price: float) -> float:
    """Compute per-share P&L of a single leg at expiration.

    P&L = direction * quantity * (intrinsic_value - premium_paid)
    where premium_paid is positive for buys, recovered for sells.
    """
    direction = _leg_direction(leg)

    if leg.option_type == "c":
        intrinsic = max(underlying_price - leg.strike, 0.0)
    else:
        intrinsic = max(leg.strike - underlying_price, 0.0)

    # Per-share P&L: direction * (intrinsic - premium) * quantity * 100
    return direction * (intrinsic - leg.premium) * leg.quantity * 100


def _strategy_pnl_at_price(legs: list[OptionLeg], price: float) -> float:
    """Sum P&L across all legs at a given underlying price."""
    return sum(_leg_payoff_at_expiration(leg, price) for leg in legs)


# ── Core analysis ────────────────────────────────────────────────────


def analyze_multi_leg(
    legs: list[OptionLeg],
    spot: float,
    dte_days: int = 30,
    risk_free_rate: float = _RISK_FREE_RATE,
    curve_points: int = 200,
) -> MultiLegResult:
    """Analyse a multi-leg options strategy.

    Args:
        legs:           List of option legs (1-4 legs).
        spot:           Current underlying price.
        dte_days:       Days to expiration (for Greeks calculation).
        risk_free_rate: Annual risk-free rate.
        curve_points:   Number of points in the P&L curve.

    Returns:
        :class:`MultiLegResult` with P&L metrics, breakevens, Greeks,
        and a P&L curve.

    Raises:
        ValueError: If legs list is empty or has more than 4 legs.
    """
    if not legs:
        raise ValueError("At least one leg is required")
    if len(legs) > 4:
        raise ValueError("Maximum 4 legs supported")
    for leg in legs:
        if leg.option_type not in ("c", "p"):
            raise ValueError(f"option_type must be 'c' or 'p', got '{leg.option_type}'")
        if leg.action not in ("buy", "sell"):
            raise ValueError(f"action must be 'buy' or 'sell', got '{leg.action}'")
        if leg.strike <= 0:
            raise ValueError(f"strike must be positive, got {leg.strike}")
        if leg.quantity < 1:
            raise ValueError(f"quantity must be >= 1, got {leg.quantity}")
        if leg.premium < 0:
            raise ValueError(f"premium must be non-negative, got {leg.premium}")

    # ── Net debit/credit ─────────────────────────────────────────
    # Positive = net debit (you pay), negative = net credit (you receive)
    net_debit_credit = sum(_leg_direction(leg) * leg.premium * leg.quantity * 100 for leg in legs)

    # ── P&L curve ────────────────────────────────────────────────
    strikes = sorted({leg.strike for leg in legs})
    min_strike = min(strikes)
    max_strike = max(strikes)
    spread = max_strike - min_strike if len(strikes) > 1 else spot * 0.15
    padding = max(spread * 1.5, spot * 0.10)

    lo = max(min_strike - padding, 0.01)
    hi = max_strike + padding
    step = (hi - lo) / curve_points

    pnl_curve: list[PnLPoint] = []
    for i in range(curve_points + 1):
        p = lo + step * i
        pnl = _strategy_pnl_at_price(legs, p)
        pnl_curve.append(PnLPoint(price=round(p, 2), pnl=round(pnl, 2)))

    # ── Max profit / max loss ────────────────────────────────────
    # Evaluate at key points: each strike, far low, far high, plus
    # between each pair of strikes.
    eval_prices = list(strikes)
    eval_prices.append(lo)
    eval_prices.append(hi)
    for i in range(len(strikes) - 1):
        eval_prices.append((strikes[i] + strikes[i + 1]) / 2.0)

    pnl_values = [_strategy_pnl_at_price(legs, p) for p in eval_prices]
    max_profit = max(pnl_values)
    max_loss = min(pnl_values)

    # Check if profit/loss is unbounded
    # For far tails, if the curve is still increasing/decreasing, it's unbounded
    pnl_at_lo = _strategy_pnl_at_price(legs, lo * 0.5) if lo > 0.02 else pnl_values[0]
    pnl_at_hi = _strategy_pnl_at_price(legs, hi * 1.5)

    if pnl_at_hi > max_profit:
        max_profit = math.inf
    if pnl_at_lo > max_profit:
        max_profit = math.inf
    if pnl_at_hi < max_loss:
        max_loss = -math.inf
    if pnl_at_lo < max_loss:
        max_loss = -math.inf

    # ── Breakeven points ─────────────────────────────────────────
    # Walk the P&L curve and find zero crossings
    breakeven_points: list[float] = []
    for i in range(len(pnl_curve) - 1):
        p1 = pnl_curve[i]
        p2 = pnl_curve[i + 1]
        if p1.pnl == 0.0:
            breakeven_points.append(p1.price)
        elif (p1.pnl > 0 and p2.pnl < 0) or (p1.pnl < 0 and p2.pnl > 0):
            # Linear interpolation
            ratio = abs(p1.pnl) / (abs(p1.pnl) + abs(p2.pnl))
            bp = p1.price + ratio * (p2.price - p1.price)
            breakeven_points.append(round(bp, 2))
    if pnl_curve and pnl_curve[-1].pnl == 0.0:
        breakeven_points.append(pnl_curve[-1].price)

    # Deduplicate close breakevens (within $0.05)
    if breakeven_points:
        deduped = [breakeven_points[0]]
        for bp in breakeven_points[1:]:
            if abs(bp - deduped[-1]) > 0.05:
                deduped.append(bp)
        breakeven_points = deduped

    # ── Aggregated Greeks ────────────────────────────────────────
    total_delta = 0.0
    total_gamma = 0.0
    total_theta = 0.0
    total_vega = 0.0
    total_rho = 0.0

    for leg in legs:
        direction = _leg_direction(leg)
        iv = leg.iv if leg.iv > 0 else 0.30

        greeks: GreeksResult = calculate_greeks(
            spot=spot,
            strike=leg.strike,
            dte_days=dte_days,
            risk_free_rate=risk_free_rate,
            iv=iv,
            option_type=leg.option_type,
        )

        total_delta += direction * leg.quantity * greeks.delta
        total_gamma += direction * leg.quantity * greeks.gamma
        total_theta += direction * leg.quantity * greeks.theta
        total_vega += direction * leg.quantity * greeks.vega
        total_rho += direction * leg.quantity * greeks.rho

    aggregated = AggregatedGreeks(
        delta=round(total_delta, 6),
        gamma=round(total_gamma, 6),
        theta=round(total_theta, 6),
        vega=round(total_vega, 6),
        rho=round(total_rho, 6),
    )

    # Convert inf to large sentinel for JSON serialisation
    max_profit_out = max_profit if math.isfinite(max_profit) else 999_999_999.0
    max_loss_out = max_loss if math.isfinite(max_loss) else -999_999_999.0

    return MultiLegResult(
        net_debit_credit=round(net_debit_credit, 2),
        max_profit=round(max_profit_out, 2),
        max_loss=round(max_loss_out, 2),
        breakeven_points=breakeven_points,
        greeks=aggregated,
        pnl_curve=pnl_curve,
    )
