from __future__ import annotations

import numpy as np
import pytest

from app.greeks import GreeksResult, bs_price_and_greeks, calculate_greeks


class TestBsPriceAndGreeks:
    def _make_arrays(
        self,
        S: float = 100.0,
        K: float = 100.0,
        T: float = 30 / 365.0,
        sigma: float = 0.25,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        return (
            np.array([S], dtype=np.float64),
            np.array([K], dtype=np.float64),
            np.array([T], dtype=np.float64),
            np.array([sigma], dtype=np.float64),
        )

    def test_atm_call_delta_near_half(self) -> None:
        S, K, T, sigma = self._make_arrays()
        _price, delta, _gamma, _theta, _vega, _rho = bs_price_and_greeks(S, K, T, 0.05, sigma, "c")
        assert 0.45 < delta[0] < 0.65

    def test_atm_put_delta_near_neg_half(self) -> None:
        S, K, T, sigma = self._make_arrays()
        _price, delta, _gamma, _theta, _vega, _rho = bs_price_and_greeks(S, K, T, 0.05, sigma, "p")
        assert -0.60 < delta[0] < -0.40

    def test_call_price_positive(self) -> None:
        S, K, T, sigma = self._make_arrays()
        price, *_ = bs_price_and_greeks(S, K, T, 0.05, sigma, "c")
        assert price[0] > 0.0

    def test_gamma_positive(self) -> None:
        S, K, T, sigma = self._make_arrays()
        _price, _delta, gamma, _theta, _vega, _rho = bs_price_and_greeks(S, K, T, 0.05, sigma, "c")
        assert gamma[0] > 0.0

    def test_vega_positive(self) -> None:
        S, K, T, sigma = self._make_arrays()
        _price, _delta, _gamma, _theta, vega, _rho = bs_price_and_greeks(S, K, T, 0.05, sigma, "c")
        assert vega[0] > 0.0

    def test_expired_call_intrinsic(self) -> None:
        S = np.array([110.0], dtype=np.float64)
        K = np.array([100.0], dtype=np.float64)
        T = np.array([0.0], dtype=np.float64)
        sigma = np.array([0.25], dtype=np.float64)
        price, delta, gamma, _theta, vega, _rho = bs_price_and_greeks(S, K, T, 0.05, sigma, "c")
        assert price[0] == pytest.approx(10.0)
        assert delta[0] == 1.0
        assert gamma[0] == 0.0
        assert vega[0] == 0.0

    def test_expired_put_intrinsic(self) -> None:
        S = np.array([90.0], dtype=np.float64)
        K = np.array([100.0], dtype=np.float64)
        T = np.array([0.0], dtype=np.float64)
        sigma = np.array([0.25], dtype=np.float64)
        price, delta, _gamma, _theta, _vega, _rho = bs_price_and_greeks(S, K, T, 0.05, sigma, "p")
        assert price[0] == pytest.approx(10.0)
        assert delta[0] == -1.0

    def test_vectorized_multiple_rows(self) -> None:
        S = np.array([100.0, 100.0, 100.0], dtype=np.float64)
        K = np.array([90.0, 100.0, 110.0], dtype=np.float64)
        T = np.full(3, 30 / 365.0, dtype=np.float64)
        sigma = np.full(3, 0.25, dtype=np.float64)
        _price, delta, _gamma, _theta, _vega, _rho = bs_price_and_greeks(S, K, T, 0.05, sigma, "c")
        assert delta[0] > delta[1] > delta[2]

    def test_rho_call_positive(self) -> None:
        S, K, T, sigma = self._make_arrays()
        _price, _delta, _gamma, _theta, _vega, rho = bs_price_and_greeks(S, K, T, 0.05, sigma, "c")
        assert rho[0] > 0.0

    def test_rho_put_negative(self) -> None:
        S, K, T, sigma = self._make_arrays()
        _price, _delta, _gamma, _theta, _vega, rho = bs_price_and_greeks(S, K, T, 0.05, sigma, "p")
        assert rho[0] < 0.0


class TestCalculateGreeks:
    def test_returns_greeks_result(self) -> None:
        result = calculate_greeks(100.0, 100.0, 30, 0.05, 0.25, "c")
        assert isinstance(result, GreeksResult)

    def test_call_delta_range(self) -> None:
        result = calculate_greeks(100.0, 100.0, 30, 0.05, 0.25, "c")
        assert 0.0 < result.delta < 1.0

    def test_put_delta_range(self) -> None:
        result = calculate_greeks(100.0, 100.0, 30, 0.05, 0.25, "p")
        assert -1.0 < result.delta < 0.0

    def test_deep_itm_call(self) -> None:
        result = calculate_greeks(200.0, 100.0, 30, 0.05, 0.25, "c")
        assert result.delta > 0.95
        assert result.price > 99.0

    def test_deep_otm_call(self) -> None:
        result = calculate_greeks(50.0, 100.0, 30, 0.05, 0.25, "c")
        assert result.delta < 0.01
        assert result.price < 0.01

    def test_invalid_option_type(self) -> None:
        with pytest.raises(ValueError, match="option_type must be"):
            calculate_greeks(100.0, 100.0, 30, 0.05, 0.25, "x")

    def test_negative_spot(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            calculate_greeks(-10.0, 100.0, 30, 0.05, 0.25, "c")

    def test_negative_iv(self) -> None:
        with pytest.raises(ValueError, match="iv must be positive"):
            calculate_greeks(100.0, 100.0, 30, 0.05, -0.25, "c")

    def test_zero_dte(self) -> None:
        result = calculate_greeks(110.0, 100.0, 0, 0.05, 0.25, "c")
        assert result.price == pytest.approx(10.0)
        assert result.delta == 1.0
