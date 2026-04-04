"""Feature engineering for ML signal scoring.

Computes 30+ features from daily OHLCV data with proper shift(1) lag
to prevent look-ahead bias. All features are computed as of the
*previous* bar so they are safe for next-bar prediction.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def compute_features(daily: pd.DataFrame) -> pd.DataFrame:
    """Build feature matrix from daily OHLCV DataFrame.

    Parameters
    ----------
    daily : pd.DataFrame
        Must have columns: Open, High, Low, Close, Volume.
        Index should be DatetimeIndex.

    Returns
    -------
    pd.DataFrame
        Feature matrix (NaN rows from warmup already dropped).
        Index aligned with ``daily``.
    """
    if daily.empty or len(daily) < 60:
        return pd.DataFrame()

    c = daily["Close"]
    h = daily["High"]
    lo = daily["Low"]
    v = daily["Volume"].replace(0, np.nan)

    feats: dict[str, pd.Series] = {}

    # ── Returns ──────────────────────────────────────────────────────
    for n in (1, 5, 10, 20):
        feats[f"ret_{n}d"] = c.pct_change(n)

    feats["log_ret_1d"] = pd.Series(np.log(c / c.shift(1)), index=daily.index)

    # ── Volatility ───────────────────────────────────────────────────
    for w in (5, 10, 20, 60):
        feats[f"vol_{w}d"] = c.pct_change().rolling(w).std() * np.sqrt(252)

    feats["vol_ratio_5_20"] = feats["vol_5d"] / feats["vol_20d"].replace(0, np.nan)

    tr = pd.concat(
        [h - lo, (h - c.shift(1)).abs(), (lo - c.shift(1)).abs()],
        axis=1,
    ).max(axis=1)
    feats["atr_14"] = tr.rolling(14).mean()
    feats["atr_pct"] = feats["atr_14"] / c

    # Parkinson volatility (high-low based)
    log_hl = pd.Series(np.log(h / lo), index=daily.index)
    feats["parkinson_vol_20"] = ((1 / (4 * np.log(2))) * (log_hl**2).rolling(20).mean() * 252).pow(0.5)

    # ── Momentum ─────────────────────────────────────────────────────
    delta = c.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain_14 = gain.rolling(14).mean()
    avg_loss_14 = loss.rolling(14).mean()
    rs = avg_gain_14 / avg_loss_14.replace(0, np.nan)
    feats["rsi_14"] = 100 - (100 / (1 + rs))

    ema12 = c.ewm(span=12, adjust=False).mean()
    ema26 = c.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    feats["macd"] = macd
    feats["macd_signal"] = signal
    feats["macd_hist"] = macd - signal

    for n in (5, 10, 20):
        feats[f"roc_{n}"] = (c / c.shift(n) - 1) * 100

    # ── Trend ────────────────────────────────────────────────────────
    for n in (5, 10, 20, 50):
        sma_n = c.rolling(n).mean()
        feats[f"sma_{n}_dist"] = (c - sma_n) / sma_n

    feats["ema_5_20_diff"] = (c.ewm(span=5, adjust=False).mean() - c.ewm(span=20, adjust=False).mean()) / c

    # Range position (where price is within 20d range)
    rh20 = h.rolling(20).max()
    rl20 = lo.rolling(20).min()
    rng = rh20 - rl20
    feats["range_pos_20"] = (c - rl20) / rng.replace(0, np.nan)

    # ── Volume ───────────────────────────────────────────────────────
    vol_sma20 = v.rolling(20).mean()
    feats["vol_ratio"] = v / vol_sma20.replace(0, np.nan)

    obv = (np.sign(c.diff()) * v).cumsum()
    feats["obv_pct_change_5"] = obv.pct_change(5)

    # ── Apply shift(1) to all features to prevent look-ahead ────────
    result = pd.DataFrame(feats, index=daily.index).shift(1)

    result = result.dropna()
    return result


def compute_labels(daily: pd.DataFrame, horizon: int = 5, threshold: float = 0.0) -> pd.Series:
    """Compute binary labels: 1 if forward return > threshold, else 0.

    Parameters
    ----------
    daily : pd.DataFrame
        Must have 'Close' column.
    horizon : int
        Forward-looking period in trading days.
    threshold : float
        Minimum return to label as positive (default 0.0 = any positive return).

    Returns
    -------
    pd.Series
        Binary labels (0/1) aligned with daily index. NaN for last *horizon* rows.
    """
    fwd = daily["Close"].pct_change(horizon).shift(-horizon)
    return (fwd > threshold).astype(float)
