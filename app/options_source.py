"""Options data source protocol and factory.

Defines the ``OptionsDataSource`` protocol that all options chain providers
must satisfy, plus a ``get_options_source`` factory for selecting the
appropriate implementation at runtime.

Current implementations:
    - ``"synthetic"``  — Black-Scholes synthetic chain from local Parquet data
                         (the default; requires no API keys or subscriptions)

Future implementations can be added by:
    1. Writing a class that satisfies the ``OptionsDataSource`` protocol.
    2. Registering it in ``get_options_source``.
"""

from __future__ import annotations

import logging

import pandas as pd

from app.synthetic_options import generate_synthetic_chain

logger = logging.getLogger(__name__)


class SyntheticBSSource:
    """Options chain source backed by Black-Scholes synthetic pricing.

    Prices are derived from the historical daily OHLCV data already
    stored in the local Parquet store — no external API calls required.
    """

    def get_historical_chain(
        self,
        symbol: str,
        stock_data: pd.DataFrame,
        *,
        num_strikes: int = 10,
        max_dte: int = 60,
        risk_free_rate: float = 0.05,
    ) -> pd.DataFrame:
        return generate_synthetic_chain(
            symbol,
            stock_data,
            num_strikes=num_strikes,
            max_dte=max_dte,
            risk_free_rate=risk_free_rate,
        )


def get_options_source(source_type: str = "synthetic") -> SyntheticBSSource:
    """Factory function for options data sources.

    Args:
        source_type: Identifier for the desired implementation.
                     Currently only ``"synthetic"`` is supported.

    Returns:
        An options data source instance.

    Raises:
        ValueError: If *source_type* is not recognised.
    """
    if source_type == "synthetic":
        return SyntheticBSSource()

    raise ValueError(f"Unknown options source type: {source_type!r}. " f"Supported types: ['synthetic']")
