"""Tests for Alpaca broker integration — all API calls mocked."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from app.models import (
    CreateOrderRequest,
    ClosePositionRequest,
    OrderSideEnum,
    OrderTypeEnum,
    PortfolioHistoryRequest,
    TimeInForceEnum,
)
from app.broker import AlpacaBroker


def _make_account(**overrides: Any) -> SimpleNamespace:
    defaults = dict(
        id="account-123",
        status="ACTIVE",
        cash="100000.00",
        equity="105000.00",
        portfolio_value="105000.00",
        buying_power="400000.00",
        long_market_value="5000.00",
        short_market_value="0.00",
        pattern_day_trader=False,
        trading_blocked=False,
        transfers_blocked=False,
        currency="USD",
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _make_order(**overrides: Any) -> SimpleNamespace:
    from alpaca.trading.enums import OrderSide, OrderType, TimeInForce

    defaults = dict(
        id="order-abc-123",
        symbol="AAPL",
        side=OrderSide.BUY,
        type=OrderType.MARKET,
        time_in_force=TimeInForce.DAY,
        qty="10",
        notional=None,
        limit_price=None,
        stop_price=None,
        filled_qty="10",
        filled_avg_price="175.50",
        status=SimpleNamespace(value="filled"),
        created_at="2026-04-05T10:00:00Z",
        updated_at="2026-04-05T10:00:01Z",
        submitted_at="2026-04-05T10:00:00Z",
        filled_at="2026-04-05T10:00:01Z",
        expired_at=None,
        canceled_at=None,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _make_position(**overrides: Any) -> SimpleNamespace:
    defaults = dict(
        symbol="AAPL",
        qty="10",
        side="long",
        market_value="1755.00",
        avg_entry_price="170.00",
        current_price="175.50",
        unrealized_pl="55.00",
        unrealized_plpc="0.0324",
        cost_basis="1700.00",
        change_today="0.0150",
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _make_portfolio_history() -> SimpleNamespace:
    return SimpleNamespace(
        timestamp=[1712300000, 1712386400],
        equity=[100000.0, 101500.0],
        profit_loss=[0.0, 1500.0],
        profit_loss_pct=[0.0, 0.015],
        base_value=100000.0,
    )


@pytest.fixture
def broker() -> AlpacaBroker:
    with patch.object(AlpacaBroker, "__init__", lambda self: None):
        b = AlpacaBroker()
        b._client = MagicMock()
        return b


class TestGetAccount:
    def test_returns_account_info(self, broker: AlpacaBroker) -> None:
        broker._client.get_account.return_value = _make_account()
        result = broker.get_account()
        assert result.id == "account-123"
        assert result.cash == 100000.0
        assert result.equity == 105000.0
        assert result.buying_power == 400000.0
        assert result.pattern_day_trader is False
        assert result.trading_blocked is False

    def test_handles_none_values(self, broker: AlpacaBroker) -> None:
        broker._client.get_account.return_value = _make_account(
            cash=None, equity=None, portfolio_value=None, buying_power=None, currency=None
        )
        result = broker.get_account()
        assert result.cash == 0.0
        assert result.equity == 0.0
        assert result.currency == "USD"


class TestSubmitOrder:
    def test_market_order(self, broker: AlpacaBroker) -> None:
        broker._client.submit_order.return_value = _make_order()
        req = CreateOrderRequest(symbol="AAPL", side=OrderSideEnum.BUY, qty=10)
        result = broker.submit_order(req)
        assert result.id == "order-abc-123"
        assert result.symbol == "AAPL"
        assert result.status == "filled"
        broker._client.submit_order.assert_called_once()

    def test_limit_order(self, broker: AlpacaBroker) -> None:
        broker._client.submit_order.return_value = _make_order()
        req = CreateOrderRequest(
            symbol="TSLA",
            side=OrderSideEnum.BUY,
            order_type=OrderTypeEnum.LIMIT,
            qty=5,
            limit_price=200.0,
        )
        result = broker.submit_order(req)
        assert result.id == "order-abc-123"

    def test_limit_order_missing_price_raises(self, broker: AlpacaBroker) -> None:
        req = CreateOrderRequest(
            symbol="TSLA",
            side=OrderSideEnum.BUY,
            order_type=OrderTypeEnum.LIMIT,
            qty=5,
        )
        with pytest.raises(ValueError, match="limit_price is required"):
            broker.submit_order(req)

    def test_stop_order(self, broker: AlpacaBroker) -> None:
        broker._client.submit_order.return_value = _make_order()
        req = CreateOrderRequest(
            symbol="SPY",
            side=OrderSideEnum.SELL,
            order_type=OrderTypeEnum.STOP,
            qty=1,
            stop_price=450.0,
        )
        result = broker.submit_order(req)
        assert result.id == "order-abc-123"

    def test_stop_order_missing_price_raises(self, broker: AlpacaBroker) -> None:
        req = CreateOrderRequest(
            symbol="SPY",
            side=OrderSideEnum.SELL,
            order_type=OrderTypeEnum.STOP,
            qty=1,
        )
        with pytest.raises(ValueError, match="stop_price is required"):
            broker.submit_order(req)

    def test_stop_limit_order(self, broker: AlpacaBroker) -> None:
        broker._client.submit_order.return_value = _make_order()
        req = CreateOrderRequest(
            symbol="QQQ",
            side=OrderSideEnum.BUY,
            order_type=OrderTypeEnum.STOP_LIMIT,
            qty=1,
            limit_price=550.0,
            stop_price=545.0,
        )
        result = broker.submit_order(req)
        assert result.id == "order-abc-123"

    def test_stop_limit_missing_prices_raises(self, broker: AlpacaBroker) -> None:
        req = CreateOrderRequest(
            symbol="QQQ",
            side=OrderSideEnum.BUY,
            order_type=OrderTypeEnum.STOP_LIMIT,
            qty=1,
            limit_price=550.0,
        )
        with pytest.raises(ValueError, match="Both limit_price and stop_price"):
            broker.submit_order(req)

    def test_notional_order(self, broker: AlpacaBroker) -> None:
        broker._client.submit_order.return_value = _make_order(notional="1000.00", qty=None)
        req = CreateOrderRequest(symbol="AAPL", side=OrderSideEnum.BUY, notional=1000.0)
        result = broker.submit_order(req)
        assert result.id == "order-abc-123"


class TestGetOrders:
    def test_list_open_orders(self, broker: AlpacaBroker) -> None:
        broker._client.get_orders.return_value = [_make_order(), _make_order(id="order-2")]
        result = broker.get_orders(status="open")
        assert len(result) == 2

    def test_list_with_symbols_filter(self, broker: AlpacaBroker) -> None:
        broker._client.get_orders.return_value = [_make_order()]
        result = broker.get_orders(symbols=["AAPL"])
        assert len(result) == 1

    def test_empty_orders(self, broker: AlpacaBroker) -> None:
        broker._client.get_orders.return_value = []
        result = broker.get_orders()
        assert result == []


class TestCancelOrder:
    def test_cancel_single(self, broker: AlpacaBroker) -> None:
        broker._client.cancel_order_by_id.return_value = None
        broker.cancel_order("order-abc-123")
        broker._client.cancel_order_by_id.assert_called_once_with("order-abc-123")

    def test_cancel_all(self, broker: AlpacaBroker) -> None:
        broker._client.cancel_orders.return_value = [SimpleNamespace(id="1"), SimpleNamespace(id="2")]
        count = broker.cancel_all_orders()
        assert count == 2


class TestPositions:
    def test_list_positions(self, broker: AlpacaBroker) -> None:
        broker._client.get_all_positions.return_value = [_make_position(), _make_position(symbol="TSLA")]
        result = broker.get_positions()
        assert len(result) == 2
        assert result[0].symbol == "AAPL"
        assert result[1].symbol == "TSLA"

    def test_get_single_position(self, broker: AlpacaBroker) -> None:
        broker._client.get_open_position.return_value = _make_position()
        result = broker.get_position("aapl")
        assert result.symbol == "AAPL"
        broker._client.get_open_position.assert_called_once_with("AAPL")

    def test_close_position_full(self, broker: AlpacaBroker) -> None:
        broker._client.close_position.return_value = _make_order()
        result = broker.close_position("AAPL")
        assert result.id == "order-abc-123"
        broker._client.close_position.assert_called_once_with("AAPL", close_options=None)

    def test_close_position_partial_qty(self, broker: AlpacaBroker) -> None:
        broker._client.close_position.return_value = _make_order()
        req = ClosePositionRequest(qty=5)
        broker.close_position("AAPL", req)
        call_args = broker._client.close_position.call_args
        assert call_args[0][0] == "AAPL"
        assert call_args[1]["close_options"] is not None

    def test_close_position_partial_percentage(self, broker: AlpacaBroker) -> None:
        broker._client.close_position.return_value = _make_order()
        req = ClosePositionRequest(percentage=50.0)
        broker.close_position("AAPL", req)
        call_args = broker._client.close_position.call_args
        assert call_args[1]["close_options"] is not None

    def test_close_all_positions(self, broker: AlpacaBroker) -> None:
        broker._client.close_all_positions.return_value = [SimpleNamespace(id="1")]
        count = broker.close_all_positions()
        assert count == 1
        broker._client.close_all_positions.assert_called_once_with(cancel_orders=True)


class TestPortfolioHistory:
    def test_default_history(self, broker: AlpacaBroker) -> None:
        broker._client.get_portfolio_history.return_value = _make_portfolio_history()
        req = PortfolioHistoryRequest()
        result = broker.get_portfolio_history(req)
        assert result.base_value == 100000.0
        assert len(result.equity) == 2
        assert len(result.profit_loss) == 2
        assert result.equity[1] == 101500.0

    def test_empty_history(self, broker: AlpacaBroker) -> None:
        broker._client.get_portfolio_history.return_value = SimpleNamespace(
            timestamp=None, equity=None, profit_loss=None, profit_loss_pct=None, base_value=None
        )
        req = PortfolioHistoryRequest()
        result = broker.get_portfolio_history(req)
        assert result.timestamp == []
        assert result.equity == []
        assert result.base_value == 0.0
