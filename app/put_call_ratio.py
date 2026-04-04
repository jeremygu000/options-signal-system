"""Put/Call Ratio analysis — volume, open interest, signal, term structure.

Provides comprehensive put/call ratio analytics for a given symbol by combining:
- Per-expiration volume and open interest ratios
- Aggregate (all expirations) ratios
- ATM-weighted ratios for cleaner signal
- Contrarian signal generation with standard thresholds
- Term structure across expirations
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date

import numpy as np
import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)


# ── Thresholds ───────────────────────────────────────────────────────

# CBOE historical statistics (2007-2022) via WallStreetCourier analysis.
# Equity-only P/C ratio daily range ~0.4-0.8, mean ~0.6.
PCR_EXTREME_FEAR: float = 1.15  # >1.15 → extreme fear → contrarian bullish
PCR_HIGH_FEAR: float = 1.00  # >1.00 → elevated fear
PCR_NEUTRAL_HIGH: float = 0.85  # upper neutral
PCR_NEUTRAL_LOW: float = 0.70  # lower neutral
PCR_HIGH_GREED: float = 0.55  # <0.55 → elevated greed
PCR_EXTREME_GREED: float = 0.45  # <0.45 → extreme greed → contrarian bearish


# ── Data classes ─────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class PCRStrikePoint:
    """Put/call ratio at a single strike."""

    strike: float
    call_volume: int
    put_volume: int
    call_oi: int
    put_oi: int
    pcr_volume: float  # put_vol / call_vol (0 if call_vol == 0)
    pcr_oi: float  # put_oi / call_oi
    moneyness: float  # strike / spot


@dataclass(frozen=True, slots=True)
class PCRTermPoint:
    """Put/call ratio for a single expiration (term structure)."""

    expiration: str
    dte_days: int
    call_volume: int
    put_volume: int
    call_oi: int
    put_oi: int
    pcr_volume: float
    pcr_oi: float


@dataclass(slots=True)
class PutCallRatioResult:
    """Complete put/call ratio analysis for a symbol."""

    symbol: str
    spot_price: float = 0.0

    # Aggregate ratios (across all analysed expirations)
    total_call_volume: int = 0
    total_put_volume: int = 0
    total_call_oi: int = 0
    total_put_oi: int = 0
    pcr_volume: float = 0.0  # total put vol / total call vol
    pcr_oi: float = 0.0  # total put OI / total call OI

    # ATM-weighted ratio (nearest expiration, ±10% of spot)
    atm_pcr_volume: float = 0.0
    atm_pcr_oi: float = 0.0

    # Signal
    signal: str = "neutral"  # extreme_fear / fear / neutral / greed / extreme_greed
    signal_description: str = ""

    # Per-strike breakdown (nearest expiration)
    strike_points: list[PCRStrikePoint] = field(default_factory=list)

    # Term structure
    term_structure: list[PCRTermPoint] = field(default_factory=list)

    # Expirations analysed
    expirations_analysed: int = 0

    error: str | None = None


# ── Public API ───────────────────────────────────────────────────────


def compute_put_call_ratio(symbol: str) -> PutCallRatioResult:
    """Run full put/call ratio analysis for a symbol.

    Fetches option chains across up to 6 nearest expirations and computes:
    - Aggregate volume and OI ratios
    - ATM-weighted ratios (nearest expiration)
    - Per-strike breakdown (nearest expiration, ±30% of spot)
    - Term structure across expirations
    - Contrarian signal based on aggregate volume ratio
    """
    result = PutCallRatioResult(symbol=symbol)

    try:
        ticker = yf.Ticker(symbol)

        hist = ticker.history(period="5d")
        if hist.empty:
            result.error = f"No price history for {symbol}"
            return result

        result.spot_price = float(hist["Close"].iloc[-1])

        expirations = ticker.options
        if not expirations:
            result.error = f"No options available for {symbol}"
            return result

        max_exp = min(6, len(expirations))
        result.expirations_analysed = max_exp

        # Accumulate across expirations
        agg_call_vol = 0
        agg_put_vol = 0
        agg_call_oi = 0
        agg_put_oi = 0

        for i, exp_str in enumerate(expirations[:max_exp]):
            try:
                chain = ticker.option_chain(exp_str)
                calls: pd.DataFrame = getattr(chain, "calls", pd.DataFrame())
                puts: pd.DataFrame = getattr(chain, "puts", pd.DataFrame())

                if calls.empty and puts.empty:
                    continue

                cv = int(calls["volume"].fillna(0).sum()) if not calls.empty else 0
                pv = int(puts["volume"].fillna(0).sum()) if not puts.empty else 0
                co = int(calls["openInterest"].fillna(0).sum()) if not calls.empty else 0
                po = int(puts["openInterest"].fillna(0).sum()) if not puts.empty else 0

                agg_call_vol += cv
                agg_put_vol += pv
                agg_call_oi += co
                agg_put_oi += po

                # Term structure point
                exp_date = pd.Timestamp(exp_str).date()
                dte = (exp_date - date.today()).days
                if dte > 0:
                    result.term_structure.append(
                        PCRTermPoint(
                            expiration=exp_str,
                            dte_days=dte,
                            call_volume=cv,
                            put_volume=pv,
                            call_oi=co,
                            put_oi=po,
                            pcr_volume=_safe_ratio(pv, cv),
                            pcr_oi=_safe_ratio(po, co),
                        )
                    )

                # Per-strike breakdown for nearest expiration only
                if i == 0:
                    result.strike_points = _extract_strike_points(calls, puts, result.spot_price)
                    result.atm_pcr_volume, result.atm_pcr_oi = _compute_atm_ratio(calls, puts, result.spot_price)

            except Exception:
                logger.debug("Skipping expiration %s for PCR", exp_str)
                continue

        # Aggregate ratios
        result.total_call_volume = agg_call_vol
        result.total_put_volume = agg_put_vol
        result.total_call_oi = agg_call_oi
        result.total_put_oi = agg_put_oi
        result.pcr_volume = _safe_ratio(agg_put_vol, agg_call_vol)
        result.pcr_oi = _safe_ratio(agg_put_oi, agg_call_oi)

        # Signal generation (use aggregate volume ratio)
        result.signal, result.signal_description = classify_pcr_signal(result.pcr_volume)

        # Sort term structure by DTE
        result.term_structure.sort(key=lambda t: t.dte_days)

    except Exception:
        logger.exception("%s: put/call ratio analysis failed", symbol)
        result.error = f"Put/call ratio analysis failed for {symbol}"

    return result


# ── Signal classification ────────────────────────────────────────────


def classify_pcr_signal(pcr: float) -> tuple[str, str]:
    """Classify a put/call ratio into a contrarian sentiment signal.

    Returns ``(signal_name, description)`` tuple.

    Thresholds based on CBOE equity-only put/call historical distribution.
    """
    if pcr >= PCR_EXTREME_FEAR:
        return (
            "extreme_fear",
            f"PCR {pcr:.2f} ≥ {PCR_EXTREME_FEAR} — extreme fear, contrarian bullish",
        )
    if pcr >= PCR_HIGH_FEAR:
        return (
            "fear",
            f"PCR {pcr:.2f} ≥ {PCR_HIGH_FEAR} — elevated fear, leaning bullish",
        )
    if pcr <= PCR_EXTREME_GREED:
        return (
            "extreme_greed",
            f"PCR {pcr:.2f} ≤ {PCR_EXTREME_GREED} — extreme greed, contrarian bearish",
        )
    if pcr <= PCR_HIGH_GREED:
        return (
            "greed",
            f"PCR {pcr:.2f} ≤ {PCR_HIGH_GREED} — elevated greed, leaning bearish",
        )
    return (
        "neutral",
        f"PCR {pcr:.2f} in neutral range ({PCR_HIGH_GREED}–{PCR_HIGH_FEAR})",
    )


# ── Helpers ──────────────────────────────────────────────────────────


def _safe_ratio(numerator: int | float, denominator: int | float) -> float:
    """Divide safely, returning 0.0 when denominator is zero."""
    if denominator == 0:
        return 0.0
    return round(float(numerator) / float(denominator), 4)


def _extract_strike_points(
    calls: pd.DataFrame,
    puts: pd.DataFrame,
    spot: float,
) -> list[PCRStrikePoint]:
    """Build per-strike P/C ratio breakdown within ±30% of spot."""
    low_bound = spot * 0.70
    high_bound = spot * 1.30

    call_map: dict[float, tuple[int, int]] = {}
    if not calls.empty:
        for _, row in calls.iterrows():
            strike = float(row["strike"])
            if low_bound <= strike <= high_bound:
                vol = int(row["volume"]) if pd.notna(row["volume"]) else 0
                oi = int(row["openInterest"]) if pd.notna(row["openInterest"]) else 0
                call_map[strike] = (vol, oi)

    put_map: dict[float, tuple[int, int]] = {}
    if not puts.empty:
        for _, row in puts.iterrows():
            strike = float(row["strike"])
            if low_bound <= strike <= high_bound:
                vol = int(row["volume"]) if pd.notna(row["volume"]) else 0
                oi = int(row["openInterest"]) if pd.notna(row["openInterest"]) else 0
                put_map[strike] = (vol, oi)

    all_strikes = sorted(set(call_map.keys()) | set(put_map.keys()))

    points: list[PCRStrikePoint] = []
    for strike in all_strikes:
        cv, co = call_map.get(strike, (0, 0))
        pv, po = put_map.get(strike, (0, 0))
        points.append(
            PCRStrikePoint(
                strike=round(strike, 2),
                call_volume=cv,
                put_volume=pv,
                call_oi=co,
                put_oi=po,
                pcr_volume=_safe_ratio(pv, cv),
                pcr_oi=_safe_ratio(po, co),
                moneyness=round(strike / spot, 4) if spot > 0 else 0.0,
            )
        )

    return points


def _compute_atm_ratio(
    calls: pd.DataFrame,
    puts: pd.DataFrame,
    spot: float,
) -> tuple[float, float]:
    """Compute ATM-weighted P/C ratio (strikes within ±10% of spot).

    Weights each strike by inverse distance from spot so ATM strikes
    contribute most heavily.  Returns ``(atm_pcr_volume, atm_pcr_oi)``.
    """
    low = spot * 0.90
    high = spot * 1.10

    weighted_call_vol = 0.0
    weighted_put_vol = 0.0
    weighted_call_oi = 0.0
    weighted_put_oi = 0.0

    def _weight(strike: float) -> float:
        dist = abs(strike - spot) / spot if spot > 0 else 1.0
        return 1.0 / (1.0 + dist * 10.0)  # ATM ≈ 1.0, ±10% ≈ 0.5

    if not calls.empty:
        for _, row in calls.iterrows():
            strike = float(row["strike"])
            if low <= strike <= high:
                w = _weight(strike)
                vol = float(row["volume"]) if pd.notna(row["volume"]) else 0.0
                oi = float(row["openInterest"]) if pd.notna(row["openInterest"]) else 0.0
                weighted_call_vol += vol * w
                weighted_call_oi += oi * w

    if not puts.empty:
        for _, row in puts.iterrows():
            strike = float(row["strike"])
            if low <= strike <= high:
                w = _weight(strike)
                vol = float(row["volume"]) if pd.notna(row["volume"]) else 0.0
                oi = float(row["openInterest"]) if pd.notna(row["openInterest"]) else 0.0
                weighted_put_vol += vol * w
                weighted_put_oi += oi * w

    atm_pcr_vol = _safe_ratio(weighted_put_vol, weighted_call_vol)
    atm_pcr_oi = _safe_ratio(weighted_put_oi, weighted_call_oi)
    return atm_pcr_vol, atm_pcr_oi
