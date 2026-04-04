"""Alpaca broker integration — paper/live trading via alpaca-py SDK."""

from __future__ import annotations

import logging
from typing import Any, cast

from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, OrderType, QueryOrderStatus, TimeInForce
from alpaca.trading.requests import (
    ClosePositionRequest as AlpacaClosePositionRequest,
    GetOrdersRequest,
    GetPortfolioHistoryRequest,
    LimitOrderRequest,
    MarketOrderRequest,
    StopLimitOrderRequest,
    StopOrderRequest,
)
from alpaca.common.exceptions import APIError

from app.config import settings
from app.models import (
    AccountInfoResponse,
    BrokerPositionResponse,
    ClosePositionRequest,
    CreateOrderRequest,
    OrderResponse,
    OrderSideEnum,
    OrderTypeEnum,
    PortfolioHistoryRequest,
    PortfolioHistoryResponse,
    TimeInForceEnum,
)

logger = logging.getLogger(__name__)

_SIDE_MAP: dict[OrderSideEnum, OrderSide] = {
    OrderSideEnum.BUY: OrderSide.BUY,
    OrderSideEnum.SELL: OrderSide.SELL,
}

_TIF_MAP: dict[TimeInForceEnum, TimeInForce] = {
    TimeInForceEnum.DAY: TimeInForce.DAY,
    TimeInForceEnum.GTC: TimeInForce.GTC,
    TimeInForceEnum.IOC: TimeInForce.IOC,
    TimeInForceEnum.FOK: TimeInForce.FOK,
}


def _str(val: Any) -> str | None:
    return str(val) if val is not None else None


class AlpacaBroker:
    def __init__(self) -> None:
        if not settings.alpaca_api_key or not settings.alpaca_api_secret:
            raise RuntimeError("ALPACA_API_KEY and ALPACA_API_SECRET must be set in .env")
        is_paper = "paper" in settings.alpaca_base_url.lower()
        self._client = TradingClient(
            api_key=settings.alpaca_api_key,
            secret_key=settings.alpaca_api_secret,
            paper=is_paper,
        )
        logger.info("AlpacaBroker initialized (paper=%s)", is_paper)

    def get_account(self) -> AccountInfoResponse:
        acct: Any = cast(Any, self._client.get_account())
        return AccountInfoResponse(
            id=str(acct.id),
            status=str(acct.status) if acct.status else "UNKNOWN",
            cash=float(acct.cash) if acct.cash else 0.0,
            equity=float(acct.equity) if acct.equity else 0.0,
            portfolio_value=float(acct.portfolio_value) if acct.portfolio_value else 0.0,
            buying_power=float(acct.buying_power) if acct.buying_power else 0.0,
            long_market_value=float(acct.long_market_value) if acct.long_market_value else 0.0,
            short_market_value=float(acct.short_market_value) if acct.short_market_value else 0.0,
            pattern_day_trader=bool(acct.pattern_day_trader),
            trading_blocked=bool(acct.trading_blocked),
            transfers_blocked=bool(acct.transfers_blocked),
            currency=str(acct.currency) if acct.currency else "USD",
        )

    def submit_order(self, req: CreateOrderRequest) -> OrderResponse:
        side = _SIDE_MAP[req.side]
        tif = _TIF_MAP[req.time_in_force]

        order_data: MarketOrderRequest | LimitOrderRequest | StopOrderRequest | StopLimitOrderRequest
        if req.order_type == OrderTypeEnum.MARKET:
            order_data = MarketOrderRequest(
                symbol=req.symbol,
                qty=req.qty,
                notional=req.notional,
                side=side,
                time_in_force=tif,
            )
        elif req.order_type == OrderTypeEnum.LIMIT:
            if req.limit_price is None:
                raise ValueError("limit_price is required for limit orders")
            order_data = LimitOrderRequest(
                symbol=req.symbol,
                qty=req.qty,
                notional=req.notional,
                side=side,
                time_in_force=tif,
                limit_price=req.limit_price,
            )
        elif req.order_type == OrderTypeEnum.STOP:
            if req.stop_price is None:
                raise ValueError("stop_price is required for stop orders")
            order_data = StopOrderRequest(
                symbol=req.symbol,
                qty=req.qty,
                side=side,
                time_in_force=tif,
                stop_price=req.stop_price,
            )
        elif req.order_type == OrderTypeEnum.STOP_LIMIT:
            if req.limit_price is None or req.stop_price is None:
                raise ValueError("Both limit_price and stop_price are required for stop-limit orders")
            order_data = StopLimitOrderRequest(
                symbol=req.symbol,
                qty=req.qty,
                side=side,
                time_in_force=tif,
                limit_price=req.limit_price,
                stop_price=req.stop_price,
            )
        else:
            raise ValueError(f"Unsupported order type: {req.order_type}")

        order = self._client.submit_order(order_data=order_data)
        return self._order_to_response(order)

    def get_orders(
        self, status: str = "open", limit: int = 50, symbols: list[str] | None = None
    ) -> list[OrderResponse]:
        status_map: dict[str, QueryOrderStatus] = {
            "open": QueryOrderStatus.OPEN,
            "closed": QueryOrderStatus.CLOSED,
            "all": QueryOrderStatus.ALL,
        }
        query_status = status_map.get(status.lower(), QueryOrderStatus.OPEN)

        filter_req = GetOrdersRequest(status=query_status, limit=limit, symbols=symbols or None)
        orders = self._client.get_orders(filter=filter_req)
        return [self._order_to_response(o) for o in orders]

    def cancel_order(self, order_id: str) -> None:
        self._client.cancel_order_by_id(order_id)

    def cancel_all_orders(self) -> int:
        responses = self._client.cancel_orders()
        return len(responses) if responses else 0

    def get_positions(self) -> list[BrokerPositionResponse]:
        positions: list[Any] = cast(list[Any], self._client.get_all_positions())
        return [
            BrokerPositionResponse(
                symbol=str(p.symbol),
                qty=_str(p.qty) or "0",
                side=str(p.side) if p.side else "long",
                market_value=_str(p.market_value),
                avg_entry_price=_str(p.avg_entry_price),
                current_price=_str(p.current_price),
                unrealized_pl=_str(p.unrealized_pl),
                unrealized_plpc=_str(p.unrealized_plpc),
                cost_basis=_str(p.cost_basis),
                change_today=_str(p.change_today),
            )
            for p in positions
        ]

    def get_position(self, symbol: str) -> BrokerPositionResponse:
        p: Any = cast(Any, self._client.get_open_position(symbol.upper()))
        return BrokerPositionResponse(
            symbol=str(p.symbol),
            qty=_str(p.qty) or "0",
            side=str(p.side) if p.side else "long",
            market_value=_str(p.market_value),
            avg_entry_price=_str(p.avg_entry_price),
            current_price=_str(p.current_price),
            unrealized_pl=_str(p.unrealized_pl),
            unrealized_plpc=_str(p.unrealized_plpc),
            cost_basis=_str(p.cost_basis),
            change_today=_str(p.change_today),
        )

    def close_position(self, symbol: str, req: ClosePositionRequest | None = None) -> OrderResponse:
        close_opts: AlpacaClosePositionRequest | None = None
        if req is not None:
            if req.percentage is not None:
                close_opts = AlpacaClosePositionRequest(percentage=str(req.percentage))
            elif req.qty is not None:
                close_opts = AlpacaClosePositionRequest(qty=str(req.qty))

        order = self._client.close_position(symbol.upper(), close_options=close_opts)
        return self._order_to_response(order)

    def close_all_positions(self) -> int:
        responses = self._client.close_all_positions(cancel_orders=True)
        return len(responses) if responses else 0

    def get_portfolio_history(self, req: PortfolioHistoryRequest) -> PortfolioHistoryResponse:
        history: Any = cast(
            Any,
            self._client.get_portfolio_history(
                history_filter=GetPortfolioHistoryRequest(
                    period=req.period,
                    timeframe=req.timeframe,
                    extended_hours=req.extended_hours,
                )
            ),
        )
        return PortfolioHistoryResponse(
            timestamp=list(history.timestamp) if history.timestamp else [],
            equity=list(history.equity) if history.equity else [],
            profit_loss=list(history.profit_loss) if history.profit_loss else [],
            profit_loss_pct=list(history.profit_loss_pct) if history.profit_loss_pct else [],
            base_value=float(history.base_value) if history.base_value else 0.0,
        )

    @staticmethod
    def _order_to_response(order: Any) -> OrderResponse:
        return OrderResponse(
            id=str(order.id),
            symbol=str(order.symbol),
            side=str(order.side.value) if order.side else "",
            order_type=str(order.type.value) if order.type else "",
            time_in_force=str(order.time_in_force.value) if order.time_in_force else "",
            qty=_str(order.qty),
            notional=_str(order.notional),
            limit_price=_str(order.limit_price),
            stop_price=_str(order.stop_price),
            filled_qty=_str(order.filled_qty),
            filled_avg_price=_str(order.filled_avg_price),
            status=str(order.status.value) if order.status else "unknown",
            created_at=_str(order.created_at),
            updated_at=_str(order.updated_at),
            submitted_at=_str(order.submitted_at),
            filled_at=_str(order.filled_at),
            expired_at=_str(order.expired_at),
            canceled_at=_str(order.canceled_at),
        )


_broker_instance: AlpacaBroker | None = None


def get_broker() -> AlpacaBroker:
    global _broker_instance
    if _broker_instance is None:
        _broker_instance = AlpacaBroker()
    return _broker_instance
