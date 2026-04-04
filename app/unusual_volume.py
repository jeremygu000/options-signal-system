"""Unusual Options Volume detection — "Smart Money" signal module.

Scans option chains for unusual activity that may indicate institutional trading:
- Volume / Open Interest ratio analysis
- Premium size classification
- Per-strike unusual activity flagging
- Multi-strike clustering detection
- Bullish / bearish signal classification
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)


# ── Thresholds ───────────────────────────────────────────────────────

# Volume / Open Interest ratio thresholds
VOI_ELEVATED: float = 2.0  # elevated activity
VOI_UNUSUAL: float = 3.0  # standard unusual threshold
VOI_HIGHLY_UNUSUAL: float = 5.0  # strong signal

# Minimum volume to consider (filter retail noise)
MIN_VOLUME: int = 100  # minimum contracts per strike
MIN_VOLUME_INSTITUTIONAL: int = 500  # institutional floor

# Premium thresholds (USD)
PREMIUM_SMALL: float = 10_000.0
PREMIUM_MEDIUM: float = 50_000.0
PREMIUM_LARGE: float = 250_000.0
PREMIUM_WHALE: float = 1_000_000.0

# Clustering
CLUSTERING_MIN_STRIKES: int = 3  # minimum unusual strikes for cluster

# Maximum expirations to scan
MAX_EXPIRATIONS: int = 6


# ── Data classes ─────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class UnusualStrike:
    """Single strike with unusual volume activity."""

    expiration: str
    dte_days: int
    strike: float
    option_type: str  # "call" | "put"
    volume: int
    open_interest: int
    voi_ratio: float
    bid: float
    ask: float
    mid_price: float
    implied_volatility: float
    premium: float  # volume × mid × 100
    moneyness: float  # strike / spot
    size_category: str  # "retail" | "small" | "medium" | "large" | "whale"


@dataclass(frozen=True, slots=True)
class ClusterSummary:
    """Summary of multi-strike clustering analysis."""

    is_clustered: bool
    pattern: str  # "call_heavy" | "put_heavy" | "call_only" | "put_only" | "balanced" | "none"
    unusual_call_count: int
    unusual_put_count: int
    total_premium: float
    total_contracts: int


@dataclass(slots=True)
class UnusualVolumeResult:
    """Complete unusual volume analysis for a symbol."""

    symbol: str
    spot_price: float = 0.0

    # Aggregate stats
    total_contracts_scanned: int = 0
    unusual_strikes_found: int = 0
    total_unusual_premium: float = 0.0

    # Signal
    signal: str = "neutral"  # "strong_bullish" | "bullish" | "neutral" | "bearish" | "strong_bearish"
    signal_description: str = ""
    score: int = 0

    # Unusual strikes (sorted by premium descending)
    strikes: list[UnusualStrike] = field(default_factory=list)

    # Clustering analysis
    cluster: ClusterSummary | None = None

    expirations_scanned: int = 0
    error: str | None = None


# ── Pure helpers ─────────────────────────────────────────────────────


def _safe_ratio(numerator: int, denominator: int) -> float:
    """Compute volume/OI ratio safely."""
    if denominator <= 0:
        return float(numerator) if numerator > 0 else 0.0
    return numerator / denominator


def classify_size(volume: int) -> str:
    """Classify contract volume into size bucket."""
    if volume >= 5000:
        return "whale"
    if volume >= 1000:
        return "large"
    if volume >= MIN_VOLUME_INSTITUTIONAL:
        return "medium"
    if volume >= MIN_VOLUME:
        return "small"
    return "retail"


def classify_premium(premium: float) -> str:
    """Classify premium amount into tier."""
    if premium >= PREMIUM_WHALE:
        return "whale"
    if premium >= PREMIUM_LARGE:
        return "large"
    if premium >= PREMIUM_MEDIUM:
        return "medium"
    if premium >= PREMIUM_SMALL:
        return "small"
    return "retail"


def compute_premium(volume: int, bid: float, ask: float) -> float:
    """Calculate total premium spent: volume × mid_price × 100."""
    mid = (bid + ask) / 2.0
    if mid <= 0.0:
        return 0.0
    return volume * mid * 100.0


def build_cluster_summary(strikes: list[UnusualStrike]) -> ClusterSummary:
    """Analyse clustering patterns across unusual strikes."""
    if not strikes:
        return ClusterSummary(
            is_clustered=False,
            pattern="none",
            unusual_call_count=0,
            unusual_put_count=0,
            total_premium=0.0,
            total_contracts=0,
        )

    call_count = sum(1 for s in strikes if s.option_type == "call")
    put_count = sum(1 for s in strikes if s.option_type == "put")
    total_premium = sum(s.premium for s in strikes)
    total_contracts = sum(s.volume for s in strikes)

    # Determine pattern
    if call_count > 0 and put_count == 0:
        pattern = "call_only"
    elif put_count > 0 and call_count == 0:
        pattern = "put_only"
    elif call_count > put_count * 2:
        pattern = "call_heavy"
    elif put_count > call_count * 2:
        pattern = "put_heavy"
    else:
        pattern = "balanced"

    # Clustered = 3+ unusual strikes concentrated in same expiration
    from collections import Counter

    exp_counts = Counter(s.expiration for s in strikes)
    max_per_exp = max(exp_counts.values()) if exp_counts else 0

    return ClusterSummary(
        is_clustered=max_per_exp >= CLUSTERING_MIN_STRIKES,
        pattern=pattern,
        unusual_call_count=call_count,
        unusual_put_count=put_count,
        total_premium=total_premium,
        total_contracts=total_contracts,
    )


def compute_signal(
    strikes: list[UnusualStrike],
    cluster: ClusterSummary,
) -> tuple[str, str, int]:
    """Classify overall signal from unusual strikes and clustering.

    Returns ``(signal_name, description, score)``.
    Score range: -10 to +10 (positive = bullish, negative = bearish).
    """
    if not strikes:
        return "neutral", "No unusual activity detected", 0

    score = 0
    reasons: list[str] = []

    # ── 1. Volume weight ──
    call_vol = sum(s.volume for s in strikes if s.option_type == "call")
    put_vol = sum(s.volume for s in strikes if s.option_type == "put")
    total = call_vol + put_vol
    if total > 0:
        call_pct = call_vol / total
        if call_pct >= 0.75:
            score += 3
            reasons.append(f"Call volume dominance ({call_pct:.0%})")
        elif call_pct >= 0.60:
            score += 1
            reasons.append(f"Call-leaning volume ({call_pct:.0%})")
        elif call_pct <= 0.25:
            score -= 3
            reasons.append(f"Put volume dominance ({1 - call_pct:.0%})")
        elif call_pct <= 0.40:
            score -= 1
            reasons.append(f"Put-leaning volume ({1 - call_pct:.0%})")

    # ── 2. Premium weight ──
    call_prem = sum(s.premium for s in strikes if s.option_type == "call")
    put_prem = sum(s.premium for s in strikes if s.option_type == "put")
    total_prem = call_prem + put_prem
    if total_prem > 0:
        call_prem_pct = call_prem / total_prem
        if call_prem_pct >= 0.75:
            score += 2
            reasons.append(f"Call premium dominance (${call_prem:,.0f})")
        elif call_prem_pct <= 0.25:
            score -= 2
            reasons.append(f"Put premium dominance (${put_prem:,.0f})")

    # ── 3. Clustering pattern ──
    if cluster.is_clustered:
        if cluster.pattern in ("call_only", "call_heavy"):
            score += 2
            reasons.append("Clustered bullish activity")
        elif cluster.pattern in ("put_only", "put_heavy"):
            score -= 2
            reasons.append("Clustered bearish activity")
        else:
            reasons.append("Clustered activity (mixed)")

    # ── 4. Whale presence ──
    whale_calls = sum(1 for s in strikes if s.option_type == "call" and s.size_category == "whale")
    whale_puts = sum(1 for s in strikes if s.option_type == "put" and s.size_category == "whale")
    if whale_calls > whale_puts:
        score += 1
        reasons.append(f"{whale_calls} whale call(s)")
    elif whale_puts > whale_calls:
        score -= 1
        reasons.append(f"{whale_puts} whale put(s)")

    # ── 5. High V/OI ratio strikes ──
    highly_unusual = [s for s in strikes if s.voi_ratio >= VOI_HIGHLY_UNUSUAL]
    if highly_unusual:
        hu_calls = sum(1 for s in highly_unusual if s.option_type == "call")
        hu_puts = sum(1 for s in highly_unusual if s.option_type == "put")
        if hu_calls > hu_puts:
            score += 1
            reasons.append(f"{hu_calls} highly unusual call strike(s)")
        elif hu_puts > hu_calls:
            score -= 1
            reasons.append(f"{hu_puts} highly unusual put strike(s)")

    # Clamp
    score = max(-10, min(10, score))

    # Classify
    if score >= 5:
        signal = "strong_bullish"
    elif score >= 2:
        signal = "bullish"
    elif score <= -5:
        signal = "strong_bearish"
    elif score <= -2:
        signal = "bearish"
    else:
        signal = "neutral"

    desc = "; ".join(reasons) if reasons else "Insufficient data for directional bias"
    return signal, desc, score


# ── Public API ───────────────────────────────────────────────────────


def compute_unusual_volume(symbol: str) -> UnusualVolumeResult:
    """Scan option chains for unusual volume activity.

    Fetches up to 6 nearest expirations and flags strikes where:
    - Volume/OI ratio >= VOI_UNUSUAL (3.0×) **and**
    - Volume >= MIN_VOLUME (100 contracts)

    Results are scored and classified into a directional smart-money signal.
    """
    result = UnusualVolumeResult(symbol=symbol)

    try:
        ticker = yf.Ticker(symbol)

        hist = ticker.history(period="5d")
        if hist.empty:
            result.error = f"No price history for {symbol}"
            return result

        result.spot_price = float(hist["Close"].iloc[-1])
        spot = result.spot_price

        expirations = ticker.options
        if not expirations:
            result.error = f"No options available for {symbol}"
            return result

        max_exp = min(MAX_EXPIRATIONS, len(expirations))
        result.expirations_scanned = max_exp

        unusual: list[UnusualStrike] = []
        total_scanned = 0

        for exp_str in expirations[:max_exp]:
            try:
                chain = ticker.option_chain(exp_str)
                calls: pd.DataFrame = getattr(chain, "calls", pd.DataFrame())
                puts: pd.DataFrame = getattr(chain, "puts", pd.DataFrame())

                exp_date = pd.Timestamp(exp_str).date()
                dte = (exp_date - date.today()).days
                if dte < 0:
                    continue

                # Scan calls
                unusual.extend(_scan_side(calls, exp_str, dte, "call", spot))
                total_scanned += len(calls) if not calls.empty else 0

                # Scan puts
                unusual.extend(_scan_side(puts, exp_str, dte, "put", spot))
                total_scanned += len(puts) if not puts.empty else 0

            except Exception:
                logger.debug("%s: failed to fetch chain for %s", symbol, exp_str)
                continue

        result.total_contracts_scanned = total_scanned

        # Sort by premium descending
        unusual.sort(key=lambda s: s.premium, reverse=True)
        result.strikes = unusual
        result.unusual_strikes_found = len(unusual)
        result.total_unusual_premium = sum(s.premium for s in unusual)

        # Clustering
        cluster = build_cluster_summary(unusual)
        result.cluster = cluster

        # Signal
        signal, desc, score = compute_signal(unusual, cluster)
        result.signal = signal
        result.signal_description = desc
        result.score = score

    except Exception:
        logger.exception("%s: unusual volume analysis failed", symbol)
        result.error = f"Unusual volume analysis failed for {symbol}"

    return result


# ── Internal helpers ─────────────────────────────────────────────────


def _scan_side(
    df: pd.DataFrame,
    expiration: str,
    dte: int,
    option_type: str,
    spot: float,
) -> list[UnusualStrike]:
    """Scan one side (calls or puts) of a chain for unusual strikes."""
    if df.empty:
        return []

    hits: list[UnusualStrike] = []

    for _, row in df.iterrows():
        vol = int(row["volume"]) if pd.notna(row.get("volume")) else 0
        oi = int(row["openInterest"]) if pd.notna(row.get("openInterest")) else 0

        if vol < MIN_VOLUME:
            continue

        voi = _safe_ratio(vol, oi)
        if voi < VOI_UNUSUAL:
            continue

        strike = float(row["strike"])
        bid = float(row["bid"]) if pd.notna(row.get("bid")) else 0.0
        ask = float(row["ask"]) if pd.notna(row.get("ask")) else 0.0
        iv = float(row["impliedVolatility"]) if pd.notna(row.get("impliedVolatility")) else 0.0
        mid = (bid + ask) / 2.0
        premium = compute_premium(vol, bid, ask)
        moneyness = strike / spot if spot > 0 else 0.0

        hits.append(
            UnusualStrike(
                expiration=expiration,
                dte_days=dte,
                strike=strike,
                option_type=option_type,
                volume=vol,
                open_interest=oi,
                voi_ratio=round(voi, 2),
                bid=bid,
                ask=ask,
                mid_price=round(mid, 4),
                implied_volatility=round(iv, 4),
                premium=round(premium, 2),
                moneyness=round(moneyness, 4),
                size_category=classify_size(vol),
            )
        )

    return hits
