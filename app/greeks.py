"""Black-Scholes Greeks calculator — vectorised and single-option interfaces.

Provides:
    - ``bs_price_and_greeks()``: Vectorised (numpy) for batch computation.
    - ``calculate_greeks()``: Single-option convenience wrapper returning a dict.

Greeks returned: **Delta, Gamma, Theta, Vega, Rho**.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy.stats import norm  # type: ignore[import-untyped]

# Small epsilon to avoid log(0) or division by zero
_EPS: float = 1e-8


@dataclass(frozen=True, slots=True)
class GreeksResult:
    """Result of a single-option Greeks calculation."""

    price: float
    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float


def bs_price_and_greeks(
    S: np.ndarray,
    K: np.ndarray,
    T: np.ndarray,
    r: float,
    sigma: np.ndarray,
    option_type: str,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Compute Black-Scholes price + Greeks for a vector of options.

    All array inputs must be 1-D arrays of the same length.

    Args:
        S:           Underlying price (per option row).
        K:           Strike price.
        T:           Time to expiration in years (DTE / 365). Must be > 0.
        r:           Risk-free rate (scalar).
        sigma:       Implied volatility (per option row).
        option_type: ``"c"`` for call, ``"p"`` for put.

    Returns:
        Tuple of ``(price, delta, gamma, theta, vega, rho)`` as numpy arrays.
        Rows where ``T <= 0`` are set to intrinsic value / zero Greeks.
    """
    valid = T > _EPS
    price = np.zeros_like(S)
    delta = np.zeros_like(S)
    gamma = np.zeros_like(S)
    theta = np.zeros_like(S)
    vega = np.zeros_like(S)
    rho = np.zeros_like(S)

    S_v = S[valid]
    K_v = K[valid]
    T_v = T[valid]
    sigma_v = sigma[valid]

    sqrt_T = np.sqrt(T_v)
    sigma_sqrt_T = sigma_v * sqrt_T

    d1 = (np.log(S_v / K_v + _EPS) + (r + 0.5 * sigma_v**2) * T_v) / (sigma_sqrt_T + _EPS)
    d2 = d1 - sigma_sqrt_T

    nd1 = norm.cdf(d1)
    nd2 = norm.cdf(d2)
    nd1_neg = norm.cdf(-d1)
    nd2_neg = norm.cdf(-d2)
    pdf_d1 = norm.pdf(d1)

    disc = np.exp(-r * T_v)

    if option_type == "c":
        price[valid] = S_v * nd1 - K_v * disc * nd2
        delta[valid] = nd1
        rho[valid] = K_v * T_v * disc * nd2 / 100.0  # per 1% rate move
    else:
        price[valid] = K_v * disc * nd2_neg - S_v * nd1_neg
        delta[valid] = nd1 - 1.0  # negative for puts
        rho[valid] = -K_v * T_v * disc * nd2_neg / 100.0

    gamma[valid] = pdf_d1 / (S_v * sigma_sqrt_T + _EPS)
    vega[valid] = S_v * pdf_d1 * sqrt_T / 100.0  # per 1% vol move

    theta_annual = -(S_v * pdf_d1 * sigma_v) / (2.0 * sqrt_T + _EPS) - r * K_v * disc
    if option_type == "c":
        theta[valid] = theta_annual / 365.0
    else:
        theta[valid] = (theta_annual + r * K_v * disc) / 365.0

    # Intrinsic value for expired/zero-time options
    expired = ~valid
    if option_type == "c":
        price[expired] = np.maximum(S[expired] - K[expired], 0.0)
        delta[expired] = (S[expired] > K[expired]).astype(float)
    else:
        price[expired] = np.maximum(K[expired] - S[expired], 0.0)
        delta[expired] = -((K[expired] > S[expired]).astype(float))

    return price, delta, gamma, theta, vega, rho


def calculate_greeks(
    spot: float,
    strike: float,
    dte_days: int,
    risk_free_rate: float,
    iv: float,
    option_type: str,
) -> GreeksResult:
    """Calculate Greeks for a single option contract.

    Args:
        spot:           Current underlying price.
        strike:         Option strike price.
        dte_days:       Days to expiration (calendar days).
        risk_free_rate: Annualised risk-free rate (e.g. 0.05 for 5%).
        iv:             Implied volatility (annualised, e.g. 0.30 for 30%).
        option_type:    ``"c"`` for call, ``"p"`` for put.

    Returns:
        :class:`GreeksResult` dataclass with price, delta, gamma, theta, vega, rho.
    """
    if option_type not in ("c", "p"):
        raise ValueError(f"option_type must be 'c' or 'p', got '{option_type}'")
    if spot <= 0 or strike <= 0:
        raise ValueError(f"spot and strike must be positive, got spot={spot}, strike={strike}")
    if iv <= 0:
        raise ValueError(f"iv must be positive, got {iv}")

    T = max(dte_days, 0) / 365.0

    S_arr = np.array([spot], dtype=np.float64)
    K_arr = np.array([strike], dtype=np.float64)
    T_arr = np.array([T], dtype=np.float64)
    sigma_arr = np.array([iv], dtype=np.float64)

    price, delta, gamma, theta, vega, rho = bs_price_and_greeks(
        S_arr, K_arr, T_arr, risk_free_rate, sigma_arr, option_type
    )

    return GreeksResult(
        price=round(float(price[0]), 6),
        delta=round(float(delta[0]), 6),
        gamma=round(float(gamma[0]), 6),
        theta=round(float(theta[0]), 6),
        vega=round(float(vega[0]), 6),
        rho=round(float(rho[0]), 6),
    )
