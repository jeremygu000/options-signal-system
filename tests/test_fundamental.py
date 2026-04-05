from __future__ import annotations

from unittest.mock import patch

import httpx
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
    _extract_income_highlights,
    _extract_price_targets,
    _extract_short_interest,
    _extract_valuation,
    _fetch_from_local_api,
    _index_to_date_str,
    _nf,
    _safe_float,
    _safe_int,
    compute_fundamental_analysis,
    format_market_cap,
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


class TestNf:
    def test_normal_value(self) -> None:
        assert _nf({"x": 1.5}, "x") == 1.5

    def test_none_value(self) -> None:
        assert _nf({"x": None}, "x") == 0.0

    def test_missing_key(self) -> None:
        assert _nf({}, "x") == 0.0

    def test_custom_default(self) -> None:
        assert _nf({}, "x", default=-1.0) == -1.0

    def test_non_numeric(self) -> None:
        assert _nf({"x": "abc"}, "x") == 0.0

    def test_string_number(self) -> None:
        assert _nf({"x": "3.14"}, "x") == pytest.approx(3.14)


_FAKE_FUND_RESPONSE: dict[str, object] = {
    "ticker": "AAPL",
    "regular_market_price": 190.5,
    "current_price": 190.5,
    "currency": "USD",
    "market_cap": 2_850_000_000_000,
    "trailing_pe": 28.5,
    "forward_pe": 25.3,
    "trailing_eps": 6.85,
    "forward_eps": 7.42,
    "price_to_book": 48.5,
    "price_to_sales_trailing_12_months": 28.3,
    "peg_ratio": 2.1,
    "enterprise_value": 2_600_000_000_000,
    "enterprise_to_ebitda": 18.5,
    "dividend_yield": 0.0042,
    "beta": 1.25,
    "target_low_price": 180.0,
    "target_high_price": 220.0,
    "target_mean_price": 205.0,
    "target_median_price": 202.5,
    "number_of_analyst_opinions": 42,
    "recommendation_key": "buy",
    "recommendation_mean": 1.8,
    "short_ratio": 0.25,
    "short_percent_of_float": 0.032,
    "shares_short": 24_000_000,
    "total_revenue": 383_285_000_000,
    "revenue_growth": 0.028,
    "gross_margins": 0.461,
    "operating_margins": 0.307,
    "profit_margins": 0.246,
    "earnings_quarterly_growth": 0.042,
}

_FAKE_REC_RESPONSE: dict[str, object] = {
    "ticker": "AAPL",
    "count": 1,
    "items": [
        {"date": "2026-03-01", "strong_buy": 8, "buy": 18, "hold": 12, "sell": 3, "strong_sell": 1},
    ],
}

_FAKE_EARN_RESPONSE: dict[str, object] = {
    "ticker": "AAPL",
    "count": 2,
    "items": [
        {"date": "2026-07-30", "eps_estimate": 2.5, "reported_eps": None, "surprise_pct": None},
        {"date": "2026-01-29", "eps_estimate": 2.21, "reported_eps": 2.34, "surprise_pct": 5.88},
    ],
}

_FAKE_UPG_RESPONSE: dict[str, object] = {
    "ticker": "AAPL",
    "count": 1,
    "items": [
        {"date": "2026-03-15", "firm": "Goldman Sachs", "to_grade": "buy", "from_grade": "neutral", "action": "up"},
    ],
}


def _make_response(json_data: dict[str, object], status: int = 200) -> httpx.Response:
    import json

    return httpx.Response(
        status_code=status,
        content=json.dumps(json_data).encode(),
        headers={"content-type": "application/json"},
    )


class TestFetchFromLocalApi:
    def test_success(self) -> None:
        def _handler(request: httpx.Request) -> httpx.Response:
            path = request.url.path
            if path.endswith("/recommendations"):
                return _make_response(_FAKE_REC_RESPONSE)  # type: ignore[arg-type]
            if path.endswith("/earnings"):
                return _make_response(_FAKE_EARN_RESPONSE)  # type: ignore[arg-type]
            if path.endswith("/upgrades"):
                return _make_response(_FAKE_UPG_RESPONSE)  # type: ignore[arg-type]
            return _make_response(_FAKE_FUND_RESPONSE)  # type: ignore[arg-type]

        transport = httpx.MockTransport(_handler)
        mock_client = httpx.Client(transport=transport)

        with patch("app.fundamental.httpx.Client", return_value=mock_client):
            result = _fetch_from_local_api("AAPL")

        assert result is not None
        assert result.symbol == "AAPL"
        assert result.spot_price == 190.5
        assert result.valuation.market_cap == 2_850_000_000_000
        assert result.valuation.trailing_pe == 28.5
        assert result.analyst_rating.recommendation_key == "buy"
        assert result.analyst_rating.strong_buy == 8
        assert result.analyst_rating.number_of_analysts == 42
        assert result.price_target.high == 220.0
        assert result.short_interest.shares_short == 24_000_000
        assert result.income.revenue == 383_285_000_000
        assert len(result.earnings_surprises) == 1
        assert result.earnings_surprises[0].eps_actual == 2.34
        assert result.next_earnings_date == "2026-07-30"
        assert len(result.upgrades_downgrades) == 1
        assert result.upgrades_downgrades[0].firm == "Goldman Sachs"

    def test_connection_error_returns_none(self) -> None:
        with patch("app.fundamental.httpx.Client") as mock_client_cls:
            mock_client_cls.return_value.__enter__ = lambda s: s
            mock_client_cls.return_value.__exit__ = lambda s, *a: None
            mock_client_cls.return_value.get.side_effect = httpx.ConnectError("refused")

            result = _fetch_from_local_api("AAPL")

        assert result is None

    def test_404_returns_none(self) -> None:
        def _handler(request: httpx.Request) -> httpx.Response:
            return _make_response({"error": "not found"}, status=404)

        transport = httpx.MockTransport(_handler)
        mock_client = httpx.Client(transport=transport)

        with patch("app.fundamental.httpx.Client", return_value=mock_client):
            result = _fetch_from_local_api("INVALID")

        assert result is None


class TestComputeFundamentalAnalysisHybrid:
    def test_uses_local_when_available(self) -> None:
        fake_result = FundamentalAnalysisResult(symbol="AAPL", spot_price=190.5)
        with patch("app.fundamental._fetch_from_local_api", return_value=fake_result) as mock_local:
            result = compute_fundamental_analysis("AAPL")

        mock_local.assert_called_once_with("AAPL")
        assert result.spot_price == 190.5

    def test_falls_back_to_yfinance(self) -> None:
        fake_yf_result = FundamentalAnalysisResult(symbol="AAPL", spot_price=191.0)
        with (
            patch("app.fundamental._fetch_from_local_api", return_value=None),
            patch("app.fundamental._fetch_from_yfinance", return_value=fake_yf_result) as mock_yf,
        ):
            result = compute_fundamental_analysis("AAPL")

        mock_yf.assert_called_once_with("AAPL")
        assert result.spot_price == 191.0
