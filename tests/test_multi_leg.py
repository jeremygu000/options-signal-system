from __future__ import annotations

import math

import pytest

from app.multi_leg import (
    AggregatedGreeks,
    MultiLegResult,
    OptionLeg,
    PnLPoint,
    analyze_multi_leg,
)


def _bull_call_spread(spot: float = 100.0) -> list[OptionLeg]:
    return [
        OptionLeg(
            option_type="c", action="buy", strike=95.0, expiration="2025-07-18", quantity=1, premium=7.0, iv=0.25
        ),
        OptionLeg(
            option_type="c", action="sell", strike=105.0, expiration="2025-07-18", quantity=1, premium=3.0, iv=0.25
        ),
    ]


def _bear_put_spread(spot: float = 100.0) -> list[OptionLeg]:
    return [
        OptionLeg(
            option_type="p", action="buy", strike=105.0, expiration="2025-07-18", quantity=1, premium=7.0, iv=0.25
        ),
        OptionLeg(
            option_type="p", action="sell", strike=95.0, expiration="2025-07-18", quantity=1, premium=3.0, iv=0.25
        ),
    ]


def _long_straddle(spot: float = 100.0) -> list[OptionLeg]:
    return [
        OptionLeg(
            option_type="c", action="buy", strike=100.0, expiration="2025-07-18", quantity=1, premium=5.0, iv=0.30
        ),
        OptionLeg(
            option_type="p", action="buy", strike=100.0, expiration="2025-07-18", quantity=1, premium=5.0, iv=0.30
        ),
    ]


def _iron_condor(spot: float = 100.0) -> list[OptionLeg]:
    return [
        OptionLeg(
            option_type="p", action="buy", strike=85.0, expiration="2025-07-18", quantity=1, premium=0.50, iv=0.30
        ),
        OptionLeg(
            option_type="p", action="sell", strike=90.0, expiration="2025-07-18", quantity=1, premium=1.50, iv=0.28
        ),
        OptionLeg(
            option_type="c", action="sell", strike=110.0, expiration="2025-07-18", quantity=1, premium=1.50, iv=0.28
        ),
        OptionLeg(
            option_type="c", action="buy", strike=115.0, expiration="2025-07-18", quantity=1, premium=0.50, iv=0.30
        ),
    ]


class TestValidation:
    def test_empty_legs_raises(self) -> None:
        with pytest.raises(ValueError, match="At least one leg"):
            analyze_multi_leg([], spot=100.0)

    def test_too_many_legs_raises(self) -> None:
        legs = [
            OptionLeg(option_type="c", action="buy", strike=100.0, expiration="2025-07-18", quantity=1, premium=5.0)
            for _ in range(5)
        ]
        with pytest.raises(ValueError, match="Maximum 4 legs"):
            analyze_multi_leg(legs, spot=100.0)

    def test_invalid_option_type_raises(self) -> None:
        leg = OptionLeg(option_type="x", action="buy", strike=100.0, expiration="2025-07-18", quantity=1, premium=5.0)
        with pytest.raises(ValueError, match="option_type must be"):
            analyze_multi_leg([leg], spot=100.0)

    def test_invalid_action_raises(self) -> None:
        leg = OptionLeg(option_type="c", action="hold", strike=100.0, expiration="2025-07-18", quantity=1, premium=5.0)
        with pytest.raises(ValueError, match="action must be"):
            analyze_multi_leg([leg], spot=100.0)

    def test_zero_strike_raises(self) -> None:
        leg = OptionLeg(option_type="c", action="buy", strike=0.0, expiration="2025-07-18", quantity=1, premium=5.0)
        with pytest.raises(ValueError, match="strike must be positive"):
            analyze_multi_leg([leg], spot=100.0)

    def test_zero_quantity_raises(self) -> None:
        leg = OptionLeg(option_type="c", action="buy", strike=100.0, expiration="2025-07-18", quantity=0, premium=5.0)
        with pytest.raises(ValueError, match="quantity must be >= 1"):
            analyze_multi_leg([leg], spot=100.0)

    def test_negative_premium_raises(self) -> None:
        leg = OptionLeg(option_type="c", action="buy", strike=100.0, expiration="2025-07-18", quantity=1, premium=-1.0)
        with pytest.raises(ValueError, match="premium must be non-negative"):
            analyze_multi_leg([leg], spot=100.0)


class TestBullCallSpread:
    def test_net_debit(self) -> None:
        result = analyze_multi_leg(_bull_call_spread(), spot=100.0)
        assert result.net_debit_credit == 400.0  # (7-3)*1*100

    def test_max_profit_capped(self) -> None:
        result = analyze_multi_leg(_bull_call_spread(), spot=100.0)
        assert result.max_profit == 600.0  # (105-95)*100 - 400 debit

    def test_max_loss_capped(self) -> None:
        result = analyze_multi_leg(_bull_call_spread(), spot=100.0)
        assert result.max_loss == -400.0  # net debit

    def test_one_breakeven(self) -> None:
        result = analyze_multi_leg(_bull_call_spread(), spot=100.0)
        assert len(result.breakeven_points) == 1
        assert abs(result.breakeven_points[0] - 99.0) < 0.5  # 95 + 4 = 99

    def test_pnl_curve_populated(self) -> None:
        result = analyze_multi_leg(_bull_call_spread(), spot=100.0)
        assert len(result.pnl_curve) > 100
        prices = [p.price for p in result.pnl_curve]
        assert prices == sorted(prices)


class TestBearPutSpread:
    def test_net_debit(self) -> None:
        result = analyze_multi_leg(_bear_put_spread(), spot=100.0)
        assert result.net_debit_credit == 400.0  # buy 7 - sell 3 = 4 * 100

    def test_max_profit_capped(self) -> None:
        result = analyze_multi_leg(_bear_put_spread(), spot=100.0)
        assert result.max_profit == 600.0  # (105-95)*100 - 400

    def test_max_loss_capped(self) -> None:
        result = analyze_multi_leg(_bear_put_spread(), spot=100.0)
        assert result.max_loss == -400.0


class TestLongStraddle:
    def test_net_debit(self) -> None:
        result = analyze_multi_leg(_long_straddle(), spot=100.0)
        assert result.net_debit_credit == 1000.0  # (5+5)*1*100

    def test_max_loss_is_debit(self) -> None:
        result = analyze_multi_leg(_long_straddle(), spot=100.0)
        assert result.max_loss == -1000.0

    def test_unbounded_profit(self) -> None:
        result = analyze_multi_leg(_long_straddle(), spot=100.0)
        assert result.max_profit == 999_999_999.0

    def test_two_breakevens(self) -> None:
        result = analyze_multi_leg(_long_straddle(), spot=100.0)
        assert len(result.breakeven_points) == 2
        lower, upper = result.breakeven_points
        assert abs(lower - 90.0) < 0.5  # 100 - 10 = 90
        assert abs(upper - 110.0) < 0.5  # 100 + 10 = 110


class TestIronCondor:
    def test_net_credit(self) -> None:
        result = analyze_multi_leg(_iron_condor(), spot=100.0)
        # sell 1.5+1.5 - buy 0.5+0.5 = 2.0 * 100 = 200 credit
        assert result.net_debit_credit == -200.0

    def test_max_profit_is_credit(self) -> None:
        result = analyze_multi_leg(_iron_condor(), spot=100.0)
        assert result.max_profit == 200.0

    def test_max_loss_capped(self) -> None:
        result = analyze_multi_leg(_iron_condor(), spot=100.0)
        # Max loss = wing width * 100 - credit = 5*100 - 200 = -300
        assert result.max_loss == -300.0

    def test_two_breakevens(self) -> None:
        result = analyze_multi_leg(_iron_condor(), spot=100.0)
        assert len(result.breakeven_points) == 2


class TestSingleLeg:
    def test_long_call(self) -> None:
        leg = OptionLeg(
            option_type="c", action="buy", strike=100.0, expiration="2025-07-18", quantity=1, premium=5.0, iv=0.25
        )
        result = analyze_multi_leg([leg], spot=100.0)
        assert result.net_debit_credit == 500.0  # 5*1*100
        assert result.max_loss == -500.0
        assert result.max_profit == 999_999_999.0

    def test_short_put(self) -> None:
        leg = OptionLeg(
            option_type="p", action="sell", strike=100.0, expiration="2025-07-18", quantity=1, premium=5.0, iv=0.25
        )
        result = analyze_multi_leg([leg], spot=100.0)
        assert result.net_debit_credit == -500.0  # credit


class TestGreeks:
    def test_bull_call_spread_positive_delta(self) -> None:
        result = analyze_multi_leg(_bull_call_spread(), spot=100.0)
        assert result.greeks.delta > 0

    def test_long_straddle_near_zero_delta(self) -> None:
        result = analyze_multi_leg(_long_straddle(), spot=100.0)
        assert abs(result.greeks.delta) < 0.15

    def test_iron_condor_near_zero_delta(self) -> None:
        result = analyze_multi_leg(_iron_condor(), spot=100.0)
        assert abs(result.greeks.delta) < 0.15

    def test_long_straddle_positive_gamma(self) -> None:
        result = analyze_multi_leg(_long_straddle(), spot=100.0)
        assert result.greeks.gamma > 0

    def test_long_straddle_positive_vega(self) -> None:
        result = analyze_multi_leg(_long_straddle(), spot=100.0)
        assert result.greeks.vega > 0

    def test_iron_condor_negative_gamma(self) -> None:
        result = analyze_multi_leg(_iron_condor(), spot=100.0)
        assert result.greeks.gamma < 0

    def test_greeks_fields_populated(self) -> None:
        result = analyze_multi_leg(_bull_call_spread(), spot=100.0)
        g = result.greeks
        assert isinstance(g.delta, float)
        assert isinstance(g.gamma, float)
        assert isinstance(g.theta, float)
        assert isinstance(g.vega, float)
        assert isinstance(g.rho, float)


class TestMultiQuantity:
    def test_two_contracts_doubles_pnl(self) -> None:
        legs_1x = [
            OptionLeg(
                option_type="c", action="buy", strike=100.0, expiration="2025-07-18", quantity=1, premium=5.0, iv=0.25
            ),
        ]
        legs_2x = [
            OptionLeg(
                option_type="c", action="buy", strike=100.0, expiration="2025-07-18", quantity=2, premium=5.0, iv=0.25
            ),
        ]
        r1 = analyze_multi_leg(legs_1x, spot=100.0)
        r2 = analyze_multi_leg(legs_2x, spot=100.0)
        assert r2.net_debit_credit == r1.net_debit_credit * 2
        assert r2.max_loss == r1.max_loss * 2


class TestServerEndpoint:
    def test_multi_leg_endpoint_success(self) -> None:
        from fastapi.testclient import TestClient

        from app.server import app

        with TestClient(app) as client:
            payload = {
                "legs": [
                    {
                        "option_type": "c",
                        "action": "buy",
                        "strike": 95.0,
                        "expiration": "2025-07-18",
                        "quantity": 1,
                        "premium": 7.0,
                        "iv": 0.25,
                    },
                    {
                        "option_type": "c",
                        "action": "sell",
                        "strike": 105.0,
                        "expiration": "2025-07-18",
                        "quantity": 1,
                        "premium": 3.0,
                        "iv": 0.25,
                    },
                ],
                "spot": 100.0,
                "dte_days": 30,
            }
            resp = client.post("/api/v1/options/multi-leg/analyze", json=payload)
            assert resp.status_code == 200
            data = resp.json()
            assert "net_debit_credit" in data
            assert "max_profit" in data
            assert "max_loss" in data
            assert "breakeven_points" in data
            assert "greeks" in data
            assert "pnl_curve" in data
            assert len(data["pnl_curve"]) > 100

    def test_multi_leg_endpoint_validation_error(self) -> None:
        from fastapi.testclient import TestClient

        from app.server import app

        with TestClient(app) as client:
            payload = {
                "legs": [
                    {
                        "option_type": "x",
                        "action": "buy",
                        "strike": 100.0,
                        "expiration": "2025-07-18",
                        "quantity": 1,
                        "premium": 5.0,
                        "iv": 0.25,
                    },
                ],
                "spot": 100.0,
            }
            resp = client.post("/api/v1/options/multi-leg/analyze", json=payload)
            assert resp.status_code == 200
            data = resp.json()
            assert data["error"] is not None
