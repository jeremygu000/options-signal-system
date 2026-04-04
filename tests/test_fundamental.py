from __future__ import annotations

import pandas as pd
import pytest

from app.fundamental import (
    AnalystRating,
    EarningsSurprise,
    FundamentalAnalysisResult,
    IncomeHighlights,
    PriceTarget,
    ShortInterest,
    UpgradeDowngrade,
    ValuationMetrics,
    _safe_float,
    _safe_int,
    format_market_cap,
    _extract_valuation,
    _extract_price_targets,
    _extract_short_interest,
    _extract_income_highlights,
    _index_to_date_str,
)


class TestSafeFloat:
    def test_normal_value(self) -> None:
        assert _safe_float({"x": 1.5}, "x") == 1.5

    def test_int_value(self) -> None:
        assert _safe_float({"x": 42}, "x") == 42.0

    def test_string_number(self) -> None:
        assert _safe_float({"x": "3.14"}, "x") == pytest.approx(3.14)

    def test_missing_key(self) -> None:
        assert _safe_float({}, "x") == 0.0

    def test_none_value(self) -> None:
        assert _safe_float({"x": None}, "x") == 0.0

    def test_custom_default(self) -> None:
        assert _safe_float({}, "x", default=-1.0) == -1.0

    def test_non_numeric_string(self) -> None:
        assert _safe_float({"x": "abc"}, "x") == 0.0


class TestSafeInt:
    def test_normal_value(self) -> None:
        assert _safe_int({"x": 42}, "x") == 42

    def test_float_value(self) -> None:
        assert _safe_int({"x": 3.7}, "x") == 3

    def test_string_number(self) -> None:
        assert _safe_int({"x": "100"}, "x") == 100

    def test_missing_key(self) -> None:
        assert _safe_int({}, "x") == 0

    def test_none_value(self) -> None:
        assert _safe_int({"x": None}, "x") == 0

    def test_custom_default(self) -> None:
        assert _safe_int({}, "x", default=-1) == -1

    def test_non_numeric_string(self) -> None:
        assert _safe_int({"x": "abc"}, "x") == 0


class TestFormatMarketCap:
    def test_trillion(self) -> None:
        assert format_market_cap(2.5e12) == "2.50T"

    def test_billion(self) -> None:
        assert format_market_cap(150e9) == "150.00B"

    def test_small_billion(self) -> None:
        assert format_market_cap(3.2e9) == "3.20B"

    def test_million(self) -> None:
        assert format_market_cap(500e6) == "500.0M"

    def test_thousand(self) -> None:
        assert format_market_cap(50_000) == "50K"

    def test_small(self) -> None:
        assert format_market_cap(999) == "999"

    def test_zero(self) -> None:
        assert format_market_cap(0) == "0"


class TestExtractValuation:
    def test_full_info(self) -> None:
        info: dict[str, object] = {
            "marketCap": 2_500_000_000_000,
            "trailingPE": 28.5,
            "forwardPE": 25.0,
            "trailingEps": 6.50,
            "forwardEps": 7.20,
            "priceToBook": 12.3,
            "priceToSalesTrailing12Months": 8.0,
            "pegRatio": 1.5,
            "enterpriseValue": 2_600_000_000_000,
            "enterpriseToEbitda": 22.0,
            "dividendYield": 0.006,
            "beta": 1.1,
        }
        v = _extract_valuation(info)
        assert v.market_cap == 2_500_000_000_000
        assert v.trailing_pe == 28.5
        assert v.forward_pe == 25.0
        assert v.trailing_eps == 6.50
        assert v.forward_eps == 7.20
        assert v.beta == 1.1
        assert v.dividend_yield == 0.006

    def test_empty_info(self) -> None:
        v = _extract_valuation({})
        assert v.market_cap == 0.0
        assert v.trailing_pe == 0.0
        assert v.beta == 0.0

    def test_frozen(self) -> None:
        v = ValuationMetrics(market_cap=100)
        with pytest.raises(AttributeError):
            v.market_cap = 200  # type: ignore[misc]


class TestExtractPriceTargets:
    def test_full_info(self) -> None:
        info: dict[str, object] = {
            "currentPrice": 185.0,
            "targetLowPrice": 150.0,
            "targetHighPrice": 220.0,
            "targetMeanPrice": 200.0,
            "targetMedianPrice": 198.0,
            "numberOfAnalystOpinions": 35,
        }
        pt = _extract_price_targets(info)
        assert pt.current == 185.0
        assert pt.low == 150.0
        assert pt.high == 220.0
        assert pt.mean == 200.0
        assert pt.number_of_analysts == 35

    def test_empty_info(self) -> None:
        pt = _extract_price_targets({})
        assert pt.current == 0.0
        assert pt.number_of_analysts == 0


class TestExtractShortInterest:
    def test_full_info(self) -> None:
        info: dict[str, object] = {
            "shortRatio": 2.5,
            "shortPercentOfFloat": 0.03,
            "sharesShort": 15_000_000,
        }
        si = _extract_short_interest(info)
        assert si.short_ratio == 2.5
        assert si.short_pct_of_float == 0.03
        assert si.shares_short == 15_000_000

    def test_empty_info(self) -> None:
        si = _extract_short_interest({})
        assert si.short_ratio == 0.0
        assert si.shares_short == 0


class TestExtractIncomeHighlights:
    def test_full_info(self) -> None:
        info: dict[str, object] = {
            "totalRevenue": 100_000_000_000,
            "revenueGrowth": 0.08,
            "grossMargins": 0.45,
            "operatingMargins": 0.30,
            "profitMargins": 0.25,
            "earningsQuarterlyGrowth": 0.12,
        }
        inc = _extract_income_highlights(info)
        assert inc.revenue == 100_000_000_000
        assert inc.revenue_growth == 0.08
        assert inc.gross_margin == 0.45
        assert inc.earnings_growth == 0.12

    def test_empty_info(self) -> None:
        inc = _extract_income_highlights({})
        assert inc.revenue == 0.0
        assert inc.earnings_growth == 0.0


class TestIndexToDateStr:
    def test_timestamp(self) -> None:
        ts = pd.Timestamp("2025-01-15 14:30:00")
        assert _index_to_date_str(ts) == "2025-01-15"

    def test_string(self) -> None:
        assert _index_to_date_str("2025-06-20 09:00:00") == "2025-06-20"


class TestFundamentalAnalysisResult:
    def test_default_values(self) -> None:
        r = FundamentalAnalysisResult(symbol="TEST")
        assert r.symbol == "TEST"
        assert r.spot_price == 0.0
        assert r.currency == "USD"
        assert r.valuation.market_cap == 0.0
        assert r.analyst_rating.recommendation_key == ""
        assert r.price_target.mean == 0.0
        assert r.short_interest.short_ratio == 0.0
        assert r.income.revenue == 0.0
        assert r.earnings_surprises == []
        assert r.upgrades_downgrades == []
        assert r.next_earnings_date is None
        assert r.error is None

    def test_earnings_surprise_frozen(self) -> None:
        e = EarningsSurprise(date="2025-01-15", eps_estimate=1.0, eps_actual=1.2, surprise_pct=20.0)
        assert e.eps_actual == 1.2
        with pytest.raises(AttributeError):
            e.eps_actual = 2.0  # type: ignore[misc]

    def test_upgrade_downgrade_frozen(self) -> None:
        u = UpgradeDowngrade(date="2025-01-15", firm="Goldman", to_grade="Buy", from_grade="Hold", action="upgrade")
        assert u.firm == "Goldman"
        with pytest.raises(AttributeError):
            u.firm = "JPM"  # type: ignore[misc]

    def test_analyst_rating_frozen(self) -> None:
        a = AnalystRating(recommendation_key="buy", recommendation_mean=2.0, number_of_analysts=10)
        assert a.recommendation_key == "buy"
        with pytest.raises(AttributeError):
            a.recommendation_key = "sell"  # type: ignore[misc]

    def test_short_interest_frozen(self) -> None:
        si = ShortInterest(short_ratio=3.5, short_pct_of_float=0.05, shares_short=1_000_000)
        assert si.short_ratio == 3.5
        with pytest.raises(AttributeError):
            si.short_ratio = 5.0  # type: ignore[misc]
