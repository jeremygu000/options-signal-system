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
from typing import Any

import httpx
import pandas as pd
import yfinance as yf

from app.config import settings

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

    Hybrid strategy:
    1. Try local yahoo-finance-data API first (reads cached Parquet files, fast).
    2. On connection failure or empty response, fall back to live yfinance calls.
    """
    local_result = _fetch_from_local_api(symbol)
    if local_result is not None:
        return local_result

    logger.info("%s: Local API unavailable, falling back to yfinance", symbol)
    return _fetch_from_yfinance(symbol)


def _fetch_from_local_api(symbol: str) -> FundamentalAnalysisResult | None:
    """Try fetching fundamental data from the local yahoo-finance-data API.

    Returns None if the API is unreachable or returns no data.
    """
    base = settings.market_data_api_url.rstrip("/")
    timeout = settings.market_data_api_timeout

    try:
        with httpx.Client(timeout=timeout) as client:
            fund_resp = client.get(
                f"{base}/api/v1/fundamentals/{symbol}",
                params={"source": "local"},
            )
            if fund_resp.status_code != 200:
                return None
            fund: dict[str, Any] = fund_resp.json()

            rec_resp = client.get(f"{base}/api/v1/fundamentals/{symbol}/recommendations")
            rec_data: dict[str, Any] = rec_resp.json() if rec_resp.status_code == 200 else {}

            earn_resp = client.get(f"{base}/api/v1/fundamentals/{symbol}/earnings")
            earn_data: dict[str, Any] = earn_resp.json() if earn_resp.status_code == 200 else {}

            upg_resp = client.get(f"{base}/api/v1/fundamentals/{symbol}/upgrades")
            upg_data: dict[str, Any] = upg_resp.json() if upg_resp.status_code == 200 else {}

    except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPError):
        return None

    spot = _nf(fund, "regular_market_price") or _nf(fund, "current_price")
    if spot == 0.0:
        return None

    rec_items: list[dict[str, Any]] = rec_data.get("items", [])
    latest_rec = rec_items[-1] if rec_items else {}
    strong_buy = int(latest_rec.get("strong_buy") or 0)
    buy = int(latest_rec.get("buy") or 0)
    hold = int(latest_rec.get("hold") or 0)
    sell = int(latest_rec.get("sell") or 0)
    strong_sell = int(latest_rec.get("strong_sell") or 0)
    total_analysts = strong_buy + buy + hold + sell + strong_sell

    earn_items: list[dict[str, Any]] = earn_data.get("items", [])
    surprises: list[EarningsSurprise] = []
    for e in earn_items:
        reported = e.get("reported_eps")
        if reported is None:
            continue
        surprises.append(
            EarningsSurprise(
                date=str(e.get("date", "")),
                eps_estimate=float(e.get("eps_estimate") or 0.0),
                eps_actual=float(reported),
                surprise_pct=float(e.get("surprise_pct") or 0.0),
            )
        )
        if len(surprises) >= 4:
            break

    next_earnings: str | None = None
    now_str = datetime.now().strftime("%Y-%m-%d")
    for e in earn_items:
        d = str(e.get("date", ""))
        if d >= now_str and e.get("reported_eps") is None:
            next_earnings = d
            break

    upg_items: list[dict[str, Any]] = upg_data.get("items", [])
    upgrades: list[UpgradeDowngrade] = [
        UpgradeDowngrade(
            date=str(u.get("date", "")),
            firm=str(u.get("firm") or ""),
            to_grade=str(u.get("to_grade") or ""),
            from_grade=str(u.get("from_grade") or ""),
            action=str(u.get("action") or ""),
        )
        for u in upg_items[:10]
    ]

    return FundamentalAnalysisResult(
        symbol=symbol,
        spot_price=spot,
        currency=str(fund.get("currency") or "USD"),
        valuation=ValuationMetrics(
            market_cap=_nf(fund, "market_cap"),
            trailing_pe=_nf(fund, "trailing_pe"),
            forward_pe=_nf(fund, "forward_pe"),
            trailing_eps=_nf(fund, "trailing_eps"),
            forward_eps=_nf(fund, "forward_eps"),
            price_to_book=_nf(fund, "price_to_book"),
            price_to_sales=_nf(fund, "price_to_sales_trailing_12_months"),
            peg_ratio=_nf(fund, "peg_ratio"),
            enterprise_value=_nf(fund, "enterprise_value"),
            ev_to_ebitda=_nf(fund, "enterprise_to_ebitda"),
            dividend_yield=_nf(fund, "dividend_yield"),
            beta=_nf(fund, "beta"),
        ),
        analyst_rating=AnalystRating(
            recommendation_key=str(fund.get("recommendation_key") or ""),
            recommendation_mean=_nf(fund, "recommendation_mean"),
            strong_buy=strong_buy,
            buy=buy,
            hold=hold,
            sell=sell,
            strong_sell=strong_sell,
            number_of_analysts=total_analysts,
        ),
        price_target=PriceTarget(
            current=_nf(fund, "current_price"),
            low=_nf(fund, "target_low_price"),
            high=_nf(fund, "target_high_price"),
            mean=_nf(fund, "target_mean_price"),
            median=_nf(fund, "target_median_price"),
            number_of_analysts=int(_nf(fund, "number_of_analyst_opinions")),
        ),
        short_interest=ShortInterest(
            short_ratio=_nf(fund, "short_ratio"),
            short_pct_of_float=_nf(fund, "short_percent_of_float"),
            shares_short=int(_nf(fund, "shares_short")),
        ),
        income=IncomeHighlights(
            revenue=_nf(fund, "total_revenue"),
            revenue_growth=_nf(fund, "revenue_growth"),
            gross_margin=_nf(fund, "gross_margins"),
            operating_margin=_nf(fund, "operating_margins"),
            profit_margin=_nf(fund, "profit_margins"),
            earnings_growth=_nf(fund, "earnings_quarterly_growth"),
        ),
        earnings_surprises=surprises,
        upgrades_downgrades=upgrades,
        next_earnings_date=next_earnings,
    )


def _nf(data: dict[str, Any], key: str, default: float = 0.0) -> float:
    val = data.get(key)
    if val is None:
        return default
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def _fetch_from_yfinance(symbol: str) -> FundamentalAnalysisResult:
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
