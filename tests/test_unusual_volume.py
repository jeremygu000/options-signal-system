from __future__ import annotations

import pytest

from app.unusual_volume import (
    ClusterSummary,
    UnusualStrike,
    UnusualVolumeResult,
    VOI_ELEVATED,
    VOI_HIGHLY_UNUSUAL,
    VOI_UNUSUAL,
    MIN_VOLUME,
    MIN_VOLUME_INSTITUTIONAL,
    PREMIUM_SMALL,
    PREMIUM_MEDIUM,
    PREMIUM_LARGE,
    PREMIUM_WHALE,
    CLUSTERING_MIN_STRIKES,
    MAX_EXPIRATIONS,
    _safe_ratio,
    classify_size,
    classify_premium,
    compute_premium,
    build_cluster_summary,
    compute_signal,
)


def _make_strike(
    *,
    option_type: str = "call",
    volume: int = 1000,
    open_interest: int = 200,
    voi_ratio: float = 5.0,
    premium: float = 50_000.0,
    size_category: str = "large",
    expiration: str = "2026-05-15",
    dte_days: int = 40,
    strike: float = 180.0,
    bid: float = 5.0,
    ask: float = 5.20,
    mid_price: float = 5.10,
    implied_volatility: float = 0.30,
    moneyness: float = 1.0,
) -> UnusualStrike:
    return UnusualStrike(
        expiration=expiration,
        dte_days=dte_days,
        strike=strike,
        option_type=option_type,
        volume=volume,
        open_interest=open_interest,
        voi_ratio=voi_ratio,
        bid=bid,
        ask=ask,
        mid_price=mid_price,
        implied_volatility=implied_volatility,
        premium=premium,
        moneyness=moneyness,
        size_category=size_category,
    )


class TestConstants:
    def test_voi_thresholds_ordered(self) -> None:
        assert VOI_ELEVATED < VOI_UNUSUAL < VOI_HIGHLY_UNUSUAL

    def test_volume_thresholds_ordered(self) -> None:
        assert MIN_VOLUME < MIN_VOLUME_INSTITUTIONAL

    def test_premium_thresholds_ordered(self) -> None:
        assert PREMIUM_SMALL < PREMIUM_MEDIUM < PREMIUM_LARGE < PREMIUM_WHALE

    def test_clustering_min_positive(self) -> None:
        assert CLUSTERING_MIN_STRIKES >= 2

    def test_max_expirations_positive(self) -> None:
        assert MAX_EXPIRATIONS >= 1


class TestSafeRatio:
    def test_normal(self) -> None:
        assert _safe_ratio(300, 100) == pytest.approx(3.0)

    def test_zero_denominator_with_numerator(self) -> None:
        assert _safe_ratio(500, 0) == 500.0

    def test_zero_both(self) -> None:
        assert _safe_ratio(0, 0) == 0.0

    def test_zero_numerator(self) -> None:
        assert _safe_ratio(0, 100) == 0.0

    def test_negative_denominator(self) -> None:
        assert _safe_ratio(100, -5) == 100.0

    def test_large_ratio(self) -> None:
        assert _safe_ratio(10000, 1) == pytest.approx(10000.0)

    def test_fractional(self) -> None:
        assert _safe_ratio(1, 3) == pytest.approx(1.0 / 3.0)


class TestClassifySize:
    def test_retail(self) -> None:
        assert classify_size(50) == "retail"

    def test_small(self) -> None:
        assert classify_size(100) == "small"

    def test_medium(self) -> None:
        assert classify_size(500) == "medium"

    def test_large(self) -> None:
        assert classify_size(1000) == "large"

    def test_whale(self) -> None:
        assert classify_size(5000) == "whale"

    def test_boundary_retail(self) -> None:
        assert classify_size(99) == "retail"

    def test_boundary_small(self) -> None:
        assert classify_size(499) == "small"


class TestClassifyPremium:
    def test_retail(self) -> None:
        assert classify_premium(5_000) == "retail"

    def test_small(self) -> None:
        assert classify_premium(10_000) == "small"

    def test_medium(self) -> None:
        assert classify_premium(50_000) == "medium"

    def test_large(self) -> None:
        assert classify_premium(250_000) == "large"

    def test_whale(self) -> None:
        assert classify_premium(1_000_000) == "whale"


class TestComputePremium:
    def test_normal(self) -> None:
        assert compute_premium(100, 5.0, 5.20) == pytest.approx(100 * 5.10 * 100)

    def test_zero_prices(self) -> None:
        assert compute_premium(100, 0.0, 0.0) == 0.0

    def test_zero_volume(self) -> None:
        assert compute_premium(0, 5.0, 5.20) == 0.0

    def test_negative_mid(self) -> None:
        assert compute_premium(100, -1.0, 0.5) == 0.0


class TestBuildClusterSummary:
    def test_empty(self) -> None:
        c = build_cluster_summary([])
        assert c.is_clustered is False
        assert c.pattern == "none"
        assert c.unusual_call_count == 0
        assert c.unusual_put_count == 0

    def test_call_only(self) -> None:
        strikes = [_make_strike(option_type="call") for _ in range(3)]
        c = build_cluster_summary(strikes)
        assert c.pattern == "call_only"
        assert c.unusual_call_count == 3
        assert c.unusual_put_count == 0
        assert c.is_clustered is True

    def test_put_only(self) -> None:
        strikes = [_make_strike(option_type="put") for _ in range(3)]
        c = build_cluster_summary(strikes)
        assert c.pattern == "put_only"
        assert c.unusual_put_count == 3

    def test_call_heavy(self) -> None:
        strikes = [
            _make_strike(option_type="call"),
            _make_strike(option_type="call"),
            _make_strike(option_type="call"),
            _make_strike(option_type="put"),
        ]
        c = build_cluster_summary(strikes)
        assert c.pattern == "call_heavy"

    def test_put_heavy(self) -> None:
        strikes = [
            _make_strike(option_type="put"),
            _make_strike(option_type="put"),
            _make_strike(option_type="put"),
            _make_strike(option_type="call"),
        ]
        c = build_cluster_summary(strikes)
        assert c.pattern == "put_heavy"

    def test_balanced(self) -> None:
        strikes = [
            _make_strike(option_type="call"),
            _make_strike(option_type="put"),
        ]
        c = build_cluster_summary(strikes)
        assert c.pattern == "balanced"

    def test_not_clustered_different_expirations(self) -> None:
        strikes = [
            _make_strike(expiration="2026-05-15"),
            _make_strike(expiration="2026-06-15"),
        ]
        c = build_cluster_summary(strikes)
        assert c.is_clustered is False

    def test_clustered_same_expiration(self) -> None:
        strikes = [
            _make_strike(strike=180.0),
            _make_strike(strike=185.0),
            _make_strike(strike=190.0),
        ]
        c = build_cluster_summary(strikes)
        assert c.is_clustered is True

    def test_total_premium(self) -> None:
        strikes = [
            _make_strike(premium=25_000.0),
            _make_strike(premium=75_000.0),
        ]
        c = build_cluster_summary(strikes)
        assert c.total_premium == pytest.approx(100_000.0)

    def test_total_contracts(self) -> None:
        strikes = [
            _make_strike(volume=500),
            _make_strike(volume=1500),
        ]
        c = build_cluster_summary(strikes)
        assert c.total_contracts == 2000


class TestComputeSignal:
    def test_empty_strikes(self) -> None:
        cluster = ClusterSummary(
            is_clustered=False,
            pattern="none",
            unusual_call_count=0,
            unusual_put_count=0,
            total_premium=0.0,
            total_contracts=0,
        )
        signal, desc, score = compute_signal([], cluster)
        assert signal == "neutral"
        assert score == 0

    def test_strong_bullish(self) -> None:
        strikes = [
            _make_strike(option_type="call", volume=6000, premium=300_000, size_category="whale", voi_ratio=6.0),
            _make_strike(option_type="call", volume=5000, premium=200_000, size_category="whale", voi_ratio=5.5),
        ]
        cluster = build_cluster_summary(strikes)
        signal, desc, score = compute_signal(strikes, cluster)
        assert signal in ("strong_bullish", "bullish")
        assert score > 0

    def test_strong_bearish(self) -> None:
        strikes = [
            _make_strike(option_type="put", volume=6000, premium=300_000, size_category="whale", voi_ratio=6.0),
            _make_strike(option_type="put", volume=5000, premium=200_000, size_category="whale", voi_ratio=5.5),
        ]
        cluster = build_cluster_summary(strikes)
        signal, desc, score = compute_signal(strikes, cluster)
        assert signal in ("strong_bearish", "bearish")
        assert score < 0

    def test_balanced_neutral(self) -> None:
        strikes = [
            _make_strike(option_type="call", volume=500, premium=25_000),
            _make_strike(option_type="put", volume=500, premium=25_000),
        ]
        cluster = build_cluster_summary(strikes)
        signal, desc, score = compute_signal(strikes, cluster)
        assert signal == "neutral"

    def test_score_clamped(self) -> None:
        strikes = [
            _make_strike(option_type="call", volume=10000, premium=2_000_000, size_category="whale", voi_ratio=10.0)
            for _ in range(10)
        ]
        cluster = build_cluster_summary(strikes)
        _, _, score = compute_signal(strikes, cluster)
        assert -10 <= score <= 10

    def test_call_premium_dominance(self) -> None:
        strikes = [
            _make_strike(option_type="call", premium=900_000),
            _make_strike(option_type="put", premium=100_000),
        ]
        cluster = build_cluster_summary(strikes)
        _, desc, score = compute_signal(strikes, cluster)
        assert score > 0

    def test_put_premium_dominance(self) -> None:
        strikes = [
            _make_strike(option_type="put", premium=900_000),
            _make_strike(option_type="call", premium=100_000),
        ]
        cluster = build_cluster_summary(strikes)
        _, desc, score = compute_signal(strikes, cluster)
        assert score < 0

    def test_whale_calls_boost(self) -> None:
        strikes = [
            _make_strike(option_type="call", volume=500, premium=25_000, size_category="whale"),
            _make_strike(option_type="put", volume=500, premium=25_000, size_category="small"),
        ]
        cluster = build_cluster_summary(strikes)
        _, _, score = compute_signal(strikes, cluster)
        assert score > 0

    def test_whale_puts_boost(self) -> None:
        strikes = [
            _make_strike(option_type="put", volume=500, premium=25_000, size_category="whale"),
            _make_strike(option_type="call", volume=500, premium=25_000, size_category="small"),
        ]
        cluster = build_cluster_summary(strikes)
        _, _, score = compute_signal(strikes, cluster)
        assert score < 0


class TestUnusualStrike:
    def test_frozen(self) -> None:
        s = _make_strike()
        with pytest.raises(AttributeError):
            s.volume = 999  # type: ignore[misc]

    def test_slots(self) -> None:
        s = _make_strike()
        assert not hasattr(s, "__dict__")


class TestClusterSummary:
    def test_frozen(self) -> None:
        c = ClusterSummary(
            is_clustered=False,
            pattern="none",
            unusual_call_count=0,
            unusual_put_count=0,
            total_premium=0.0,
            total_contracts=0,
        )
        with pytest.raises(AttributeError):
            c.is_clustered = True  # type: ignore[misc]


class TestUnusualVolumeResult:
    def test_defaults(self) -> None:
        r = UnusualVolumeResult(symbol="AAPL")
        assert r.symbol == "AAPL"
        assert r.spot_price == 0.0
        assert r.strikes == []
        assert r.cluster is None
        assert r.error is None

    def test_mutable(self) -> None:
        r = UnusualVolumeResult(symbol="AAPL")
        r.signal = "bullish"
        assert r.signal == "bullish"

    def test_error_field(self) -> None:
        r = UnusualVolumeResult(symbol="AAPL")
        r.error = "some error"
        assert r.error == "some error"
