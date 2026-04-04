"""Fundamental analysis — earnings, valuation, analyst ratings, short interest.

Provides fundamental data for a given symbol by combining:
- Valuation metrics (P/E, EPS, market cap, book value)
- Analyst consensus (recommendations, price targets, upgrades/downgrades)
- Earnings data (recent EPS surprises, next earnings date)
- Short interest (short ratio, short % of float)
- Income statement highlights (revenue growth, profit margins)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)


# ── Data classes ─────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ValuationMetrics:
    """Key valuation ratios and market data."""

    market_cap: float = 0.0  # in USD
    trailing_pe: float = 0.0
    forward_pe: float = 0.0
    trailing_eps: float = 0.0
    forward_eps: float = 0.0
    price_to_book: float = 0.0
    price_to_sales: float = 0.0
    peg_ratio: float = 0.0
    enterprise_value: float = 0.0
    ev_to_ebitda: float = 0.0
    dividend_yield: float = 0.0  # decimal, e.g. 0.02 = 2%
    beta: float = 0.0


@dataclass(frozen=True, slots=True)
class AnalystRating:
    """Analyst recommendation summary."""

    recommendation_key: str = ""  # e.g. "buy", "hold", "sell"
    recommendation_mean: float = 0.0  # 1.0 = strong buy, 5.0 = strong sell
    strong_buy: int = 0
    buy: int = 0
    hold: int = 0
    sell: int = 0
    strong_sell: int = 0
    number_of_analysts: int = 0


@dataclass(frozen=True, slots=True)
class PriceTarget:
    """Analyst price target summary."""

    current: float = 0.0
    low: float = 0.0
    high: float = 0.0
    mean: float = 0.0
    median: float = 0.0
    number_of_analysts: int = 0


@dataclass(frozen=True, slots=True)
class EarningsSurprise:
    """Single earnings report vs estimate."""

    date: str  # YYYY-MM-DD
    eps_estimate: float = 0.0
    eps_actual: float = 0.0
    surprise_pct: float = 0.0  # positive = beat


@dataclass(frozen=True, slots=True)
class UpgradeDowngrade:
    """Single analyst rating change."""

    date: str
    firm: str
    to_grade: str
    from_grade: str
    action: str  # e.g. "upgrade", "downgrade", "init"


@dataclass(frozen=True, slots=True)
class ShortInterest:
    """Short selling interest metrics."""

    short_ratio: float = 0.0  # days to cover
    short_pct_of_float: float = 0.0  # decimal, e.g. 0.05 = 5%
    shares_short: int = 0


@dataclass(frozen=True, slots=True)
class IncomeHighlights:
    """Key income statement metrics."""

    revenue: float = 0.0
    revenue_growth: float = 0.0  # QoQ or YoY decimal
    gross_margin: float = 0.0  # decimal
    operating_margin: float = 0.0  # decimal
    profit_margin: float = 0.0  # decimal
    earnings_growth: float = 0.0  # quarterly growth decimal


@dataclass(slots=True)
class FundamentalAnalysisResult:
    """Complete fundamental analysis for a symbol."""

    symbol: str
    spot_price: float = 0.0
    currency: str = "USD"

    valuation: ValuationMetrics = field(default_factory=ValuationMetrics)
    analyst_rating: AnalystRating = field(default_factory=AnalystRating)
    price_target: PriceTarget = field(default_factory=PriceTarget)
    short_interest: ShortInterest = field(default_factory=ShortInterest)
    income: IncomeHighlights = field(default_factory=IncomeHighlights)

    # Earnings surprises (most recent 4 quarters)
    earnings_surprises: list[EarningsSurprise] = field(default_factory=list)

    # Recent upgrades/downgrades (last 10)
    upgrades_downgrades: list[UpgradeDowngrade] = field(default_factory=list)

    # Next earnings date (if available)
    next_earnings_date: str | None = None

    error: str | None = None


# ── Public API ───────────────────────────────────────────────────────


def compute_fundamental_analysis(symbol: str) -> FundamentalAnalysisResult:
    """Run full fundamental analysis for a symbol.

    Fetches fundamental data from yfinance including:
    - Valuation metrics (P/E, EPS, market cap, book value)
    - Analyst consensus (recommendations, price targets)
    - Earnings surprises (recent 4 quarters)
    - Upgrades/downgrades (recent 10)
    - Short interest (ratio, % of float)
    - Income highlights (margins, growth)
    """
    result = FundamentalAnalysisResult(symbol=symbol)

    try:
        ticker = yf.Ticker(symbol)
        info: dict[str, object] = ticker.info

        if not info or info.get("regularMarketPrice") is None:
            price = _safe_float(info, "currentPrice")
            if price == 0.0:
                result.error = f"No fundamental data for {symbol}"
                return result
            result.spot_price = price
        else:
            result.spot_price = _safe_float(info, "regularMarketPrice")

        result.currency = str(info.get("currency", "USD"))

        result.valuation = _extract_valuation(info)
        result.analyst_rating = _extract_analyst_rating(ticker)
        result.price_target = _extract_price_targets(info)
        result.short_interest = _extract_short_interest(info)
        result.income = _extract_income_highlights(info)
        result.earnings_surprises = _extract_earnings_surprises(ticker)
        result.upgrades_downgrades = _extract_upgrades_downgrades(ticker)
        result.next_earnings_date = _extract_next_earnings_date(ticker)

    except Exception:
        logger.exception("%s: Fundamental analysis failed", symbol)
        result.error = f"Fundamental analysis failed for {symbol}"

    return result


# ── Helper: safe field extraction ────────────────────────────────────


def _safe_float(info: dict[str, object], key: str, default: float = 0.0) -> float:
    """Safely extract a float from the info dict."""
    val = info.get(key)
    if val is None:
        return default
    try:
        return float(str(val))
    except (TypeError, ValueError):
        return default


def _safe_int(info: dict[str, object], key: str, default: int = 0) -> int:
    """Safely extract an int from the info dict."""
    val = info.get(key)
    if val is None:
        return default
    try:
        return int(float(str(val)))
    except (TypeError, ValueError):
        return default


# ── Valuation ────────────────────────────────────────────────────────


def _extract_valuation(info: dict[str, object]) -> ValuationMetrics:
    """Extract valuation metrics from yfinance info dict."""
    return ValuationMetrics(
        market_cap=_safe_float(info, "marketCap"),
        trailing_pe=_safe_float(info, "trailingPE"),
        forward_pe=_safe_float(info, "forwardPE"),
        trailing_eps=_safe_float(info, "trailingEps"),
        forward_eps=_safe_float(info, "forwardEps"),
        price_to_book=_safe_float(info, "priceToBook"),
        price_to_sales=_safe_float(info, "priceToSalesTrailing12Months"),
        peg_ratio=_safe_float(info, "pegRatio"),
        enterprise_value=_safe_float(info, "enterpriseValue"),
        ev_to_ebitda=_safe_float(info, "enterpriseToEbitda"),
        dividend_yield=_safe_float(info, "dividendYield"),
        beta=_safe_float(info, "beta"),
    )


# ── Analyst Ratings ──────────────────────────────────────────────────


def _extract_analyst_rating(ticker: yf.Ticker) -> AnalystRating:
    """Extract analyst recommendation from yfinance ticker."""
    info = ticker.info
    rec_key = str(info.get("recommendationKey", ""))
    rec_mean = _safe_float(info, "recommendationMean")

    strong_buy = buy = hold = sell = strong_sell = 0
    try:
        recs: pd.DataFrame = ticker.recommendations
        if recs is not None and not recs.empty:
            latest = recs.iloc[-1]
            strong_buy = int(latest.get("strongBuy", 0))
            buy = int(latest.get("buy", 0))
            hold = int(latest.get("hold", 0))
            sell = int(latest.get("sell", 0))
            strong_sell = int(latest.get("strongSell", 0))
    except Exception:
        logger.debug("Could not extract recommendation breakdown for %s", ticker.ticker)

    total = strong_buy + buy + hold + sell + strong_sell

    return AnalystRating(
        recommendation_key=rec_key,
        recommendation_mean=rec_mean,
        strong_buy=strong_buy,
        buy=buy,
        hold=hold,
        sell=sell,
        strong_sell=strong_sell,
        number_of_analysts=total,
    )


# ── Price Targets ────────────────────────────────────────────────────


def _extract_price_targets(info: dict[str, object]) -> PriceTarget:
    """Extract analyst price target data."""
    return PriceTarget(
        current=_safe_float(info, "currentPrice"),
        low=_safe_float(info, "targetLowPrice"),
        high=_safe_float(info, "targetHighPrice"),
        mean=_safe_float(info, "targetMeanPrice"),
        median=_safe_float(info, "targetMedianPrice"),
        number_of_analysts=_safe_int(info, "numberOfAnalystOpinions"),
    )


# ── Short Interest ───────────────────────────────────────────────────


def _extract_short_interest(info: dict[str, object]) -> ShortInterest:
    """Extract short interest metrics."""
    return ShortInterest(
        short_ratio=_safe_float(info, "shortRatio"),
        short_pct_of_float=_safe_float(info, "shortPercentOfFloat"),
        shares_short=_safe_int(info, "sharesShort"),
    )


# ── Income Highlights ────────────────────────────────────────────────


def _extract_income_highlights(info: dict[str, object]) -> IncomeHighlights:
    """Extract key income statement metrics."""
    return IncomeHighlights(
        revenue=_safe_float(info, "totalRevenue"),
        revenue_growth=_safe_float(info, "revenueGrowth"),
        gross_margin=_safe_float(info, "grossMargins"),
        operating_margin=_safe_float(info, "operatingMargins"),
        profit_margin=_safe_float(info, "profitMargins"),
        earnings_growth=_safe_float(info, "earningsQuarterlyGrowth"),
    )


# ── Earnings Surprises ──────────────────────────────────────────────


def _extract_earnings_surprises(ticker: yf.Ticker) -> list[EarningsSurprise]:
    """Extract recent earnings surprises from earnings_dates."""
    surprises: list[EarningsSurprise] = []
    try:
        ed: pd.DataFrame = ticker.earnings_dates
        if ed is None or ed.empty:
            return surprises

        for idx, row in ed.iterrows():
            eps_est = row.get("EPS Estimate")
            eps_actual = row.get("Reported EPS")

            if pd.isna(eps_actual):
                continue

            surprise_pct = row.get("Surprise(%)")
            date_str = _index_to_date_str(idx)

            surprises.append(
                EarningsSurprise(
                    date=date_str,
                    eps_estimate=float(eps_est) if not pd.isna(eps_est) else 0.0,
                    eps_actual=float(eps_actual),
                    surprise_pct=float(surprise_pct) if not pd.isna(surprise_pct) else 0.0,
                )
            )

            if len(surprises) >= 4:
                break

    except Exception:
        logger.debug("Could not extract earnings surprises for %s", ticker.ticker)

    return surprises


# ── Upgrades / Downgrades ───────────────────────────────────────────


def _extract_upgrades_downgrades(ticker: yf.Ticker) -> list[UpgradeDowngrade]:
    """Extract recent analyst upgrades/downgrades."""
    changes: list[UpgradeDowngrade] = []
    try:
        ud: pd.DataFrame = ticker.upgrades_downgrades
        if ud is None or ud.empty:
            return changes

        recent = ud.head(10)
        for idx, row in recent.iterrows():
            date_str = _index_to_date_str(idx)
            changes.append(
                UpgradeDowngrade(
                    date=date_str,
                    firm=str(row.get("Firm", "")),
                    to_grade=str(row.get("ToGrade", "")),
                    from_grade=str(row.get("FromGrade", "")),
                    action=str(row.get("Action", "")),
                )
            )

    except Exception:
        logger.debug("Could not extract upgrades/downgrades for %s", ticker.ticker)

    return changes


# ── Next Earnings Date ──────────────────────────────────────────────


def _extract_next_earnings_date(ticker: yf.Ticker) -> str | None:
    """Extract the next upcoming earnings date."""
    try:
        ed: pd.DataFrame = ticker.earnings_dates
        if ed is None or ed.empty:
            return None

        now = pd.Timestamp.now(tz="America/New_York")
        for idx in ed.index:
            ts = pd.Timestamp(idx)
            if ts.tzinfo is None:
                ts = ts.tz_localize("America/New_York")
            if ts >= now:
                return ts.strftime("%Y-%m-%d")
        return None

    except Exception:
        logger.debug("Could not extract next earnings date for %s", ticker.ticker)
        return None


# ── Utilities ────────────────────────────────────────────────────────


def _index_to_date_str(idx: object) -> str:
    """Convert a DataFrame index value to a date string."""
    if isinstance(idx, pd.Timestamp):
        return idx.strftime("%Y-%m-%d")
    if isinstance(idx, datetime):
        return idx.strftime("%Y-%m-%d")
    return str(idx)[:10]


def format_market_cap(value: float) -> str:
    """Format market cap for display (e.g. 2.5T, 150B, 3.2B)."""
    if value >= 1e12:
        return f"{value / 1e12:.2f}T"
    if value >= 1e9:
        return f"{value / 1e9:.2f}B"
    if value >= 1e6:
        return f"{value / 1e6:.1f}M"
    if value >= 1e3:
        return f"{value / 1e3:.0f}K"
    return f"{value:.0f}"
