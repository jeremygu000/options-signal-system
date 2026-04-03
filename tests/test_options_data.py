from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from app.options_data import (
    _transform_to_optopsy,
    clear_chain_cache,
    get_expirations,
    get_options_chain,
    get_options_chain_multi,
)


def _make_calls_df(n: int = 5, base_strike: float = 50.0) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "contractSymbol": [f"USO250418C{int(base_strike + i * 2):08d}" for i in range(n)],
            "strike": [base_strike + i * 2 for i in range(n)],
            "bid": [2.0 - i * 0.3 for i in range(n)],
            "ask": [2.2 - i * 0.3 for i in range(n)],
            "volume": [100 + i * 10 for i in range(n)],
            "openInterest": [500 + i * 50 for i in range(n)],
            "impliedVolatility": [0.35 + i * 0.02 for i in range(n)],
            "inTheMoney": [True if i < 2 else False for i in range(n)],
        }
    )


def _make_puts_df(n: int = 5, base_strike: float = 50.0) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "contractSymbol": [f"USO250418P{int(base_strike + i * 2):08d}" for i in range(n)],
            "strike": [base_strike + i * 2 for i in range(n)],
            "bid": [0.5 + i * 0.3 for i in range(n)],
            "ask": [0.7 + i * 0.3 for i in range(n)],
            "volume": [80 + i * 10 for i in range(n)],
            "openInterest": [400 + i * 50 for i in range(n)],
            "impliedVolatility": [0.30 + i * 0.02 for i in range(n)],
            "inTheMoney": [False if i < 3 else True for i in range(n)],
        }
    )


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    clear_chain_cache()


class TestTransformToOptopsy:
    def test_basic_transform(self) -> None:
        calls = _make_calls_df()
        puts = _make_puts_df()
        result = _transform_to_optopsy("USO", "2025-04-18", calls, puts)

        assert not result.empty
        assert len(result) == 10
        assert set(result.columns) >= {
            "underlying_symbol",
            "option_type",
            "expiration",
            "quote_date",
            "strike",
            "bid",
            "ask",
            "delta",
        }

    def test_option_types(self) -> None:
        calls = _make_calls_df()
        puts = _make_puts_df()
        result = _transform_to_optopsy("USO", "2025-04-18", calls, puts)

        call_rows = result[result["option_type"] == "c"]
        put_rows = result[result["option_type"] == "p"]
        assert len(call_rows) == 5
        assert len(put_rows) == 5

    def test_delta_approximation_calls(self) -> None:
        calls = _make_calls_df()
        result = _transform_to_optopsy("USO", "2025-04-18", calls, pd.DataFrame())

        itm_deltas = result[result.index < 2]["delta"]
        otm_deltas = result[result.index >= 2]["delta"]
        assert all(d == 0.65 for d in itm_deltas)
        assert all(d == 0.30 for d in otm_deltas)

    def test_delta_approximation_puts(self) -> None:
        puts = _make_puts_df()
        result = _transform_to_optopsy("USO", "2025-04-18", pd.DataFrame(), puts)

        otm_deltas = result[result.index < 3]["delta"]
        itm_deltas = result[result.index >= 3]["delta"]
        assert all(d == -0.30 for d in otm_deltas)
        assert all(d == -0.65 for d in itm_deltas)

    def test_empty_input(self) -> None:
        result = _transform_to_optopsy("USO", "2025-04-18", pd.DataFrame(), pd.DataFrame())
        assert result.empty

    def test_underlying_symbol_uppercased(self) -> None:
        calls = _make_calls_df(n=1)
        result = _transform_to_optopsy("uso", "2025-04-18", calls, pd.DataFrame())
        assert result["underlying_symbol"].iloc[0] == "USO"

    def test_expiration_is_timestamp(self) -> None:
        calls = _make_calls_df(n=1)
        result = _transform_to_optopsy("USO", "2025-04-18", calls, pd.DataFrame())
        assert isinstance(result["expiration"].iloc[0], pd.Timestamp)

    def test_quote_date_is_today(self) -> None:
        calls = _make_calls_df(n=1)
        result = _transform_to_optopsy("USO", "2025-04-18", calls, pd.DataFrame())
        assert result["quote_date"].iloc[0].date() == date.today()


class TestGetExpirations:
    @patch("app.options_data.yf.Ticker")
    def test_returns_sorted_expirations(self, mock_ticker_cls: MagicMock) -> None:
        mock_ticker = MagicMock()
        mock_ticker.options = ("2025-05-16", "2025-04-18", "2025-06-20")
        mock_ticker_cls.return_value = mock_ticker

        result = get_expirations("USO")
        assert result == ["2025-04-18", "2025-05-16", "2025-06-20"]

    @patch("app.options_data.yf.Ticker")
    def test_handles_exception(self, mock_ticker_cls: MagicMock) -> None:
        mock_ticker_cls.side_effect = RuntimeError("network error")
        result = get_expirations("USO")
        assert result == []


class TestGetOptionsChain:
    @patch("app.options_data.yf.Ticker")
    def test_fetches_and_transforms(self, mock_ticker_cls: MagicMock) -> None:
        mock_ticker = MagicMock()
        mock_ticker.options = ("2025-04-18",)
        mock_chain = MagicMock()
        mock_chain.calls = _make_calls_df()
        mock_chain.puts = _make_puts_df()
        mock_ticker.option_chain.return_value = mock_chain
        mock_ticker_cls.return_value = mock_ticker

        result = get_options_chain("USO", "2025-04-18")
        assert not result.empty
        assert len(result) == 10

    @patch("app.options_data.yf.Ticker")
    def test_uses_nearest_when_no_expiration(self, mock_ticker_cls: MagicMock) -> None:
        mock_ticker = MagicMock()
        mock_ticker.options = ("2025-04-18", "2025-05-16")
        mock_chain = MagicMock()
        mock_chain.calls = _make_calls_df(n=2)
        mock_chain.puts = _make_puts_df(n=2)
        mock_ticker.option_chain.return_value = mock_chain
        mock_ticker_cls.return_value = mock_ticker

        result = get_options_chain("USO")
        mock_ticker.option_chain.assert_called_once_with("2025-04-18")
        assert not result.empty

    @patch("app.options_data.yf.Ticker")
    def test_handles_no_expirations(self, mock_ticker_cls: MagicMock) -> None:
        mock_ticker = MagicMock()
        mock_ticker.options = ()
        mock_ticker_cls.return_value = mock_ticker

        result = get_options_chain("USO")
        assert result.empty

    @patch("app.options_data.yf.Ticker")
    def test_caches_result(self, mock_ticker_cls: MagicMock) -> None:
        mock_ticker = MagicMock()
        mock_ticker.options = ("2025-04-18",)
        mock_chain = MagicMock()
        mock_chain.calls = _make_calls_df(n=1)
        mock_chain.puts = _make_puts_df(n=1)
        mock_ticker.option_chain.return_value = mock_chain
        mock_ticker_cls.return_value = mock_ticker

        r1 = get_options_chain("USO", "2025-04-18")
        r2 = get_options_chain("USO", "2025-04-18")
        assert mock_ticker.option_chain.call_count == 1
        assert len(r1) == len(r2)


class TestGetOptionsChainMulti:
    @patch("app.options_data.get_options_chain")
    @patch("app.options_data.get_expirations")
    def test_fetches_multiple_expirations(
        self,
        mock_expirations: MagicMock,
        mock_chain: MagicMock,
    ) -> None:
        mock_expirations.return_value = ["2025-04-18", "2025-05-16", "2025-06-20"]
        mock_chain.return_value = _transform_to_optopsy("USO", "2025-04-18", _make_calls_df(n=2), _make_puts_df(n=2))

        result = get_options_chain_multi("USO", max_expirations=2)
        assert not result.empty
        assert mock_chain.call_count == 2

    @patch("app.options_data.get_expirations")
    def test_handles_no_expirations(self, mock_expirations: MagicMock) -> None:
        mock_expirations.return_value = []
        result = get_options_chain_multi("USO")
        assert result.empty
