from __future__ import annotations

import pandas as pd
import pytest

from app.put_call_ratio import (
    PCR_EXTREME_FEAR,
    PCR_EXTREME_GREED,
    PCR_HIGH_FEAR,
    PCR_HIGH_GREED,
    PCRStrikePoint,
    PCRTermPoint,
    PutCallRatioResult,
    _compute_atm_ratio,
    _extract_strike_points,
    _safe_ratio,
    classify_pcr_signal,
)


class TestSafeRatio:
    def test_normal(self) -> None:
        assert _safe_ratio(100, 200) == 0.5

    def test_zero_denominator(self) -> None:
        assert _safe_ratio(100, 0) == 0.0

    def test_zero_numerator(self) -> None:
        assert _safe_ratio(0, 200) == 0.0

    def test_both_zero(self) -> None:
        assert _safe_ratio(0, 0) == 0.0

    def test_rounding(self) -> None:
        assert _safe_ratio(1, 3) == 0.3333

    def test_large_values(self) -> None:
        assert _safe_ratio(1_000_000, 500_000) == 2.0

    def test_float_inputs(self) -> None:
        assert _safe_ratio(10.5, 5.0) == 2.1


class TestClassifyPcrSignal:
    def test_extreme_fear(self) -> None:
        signal, desc = classify_pcr_signal(1.20)
        assert signal == "extreme_fear"
        assert "contrarian bullish" in desc

    def test_fear(self) -> None:
        signal, _ = classify_pcr_signal(1.05)
        assert signal == "fear"

    def test_neutral(self) -> None:
        signal, _ = classify_pcr_signal(0.75)
        assert signal == "neutral"

    def test_greed(self) -> None:
        signal, _ = classify_pcr_signal(0.50)
        assert signal == "greed"

    def test_extreme_greed(self) -> None:
        signal, desc = classify_pcr_signal(0.40)
        assert signal == "extreme_greed"
        assert "contrarian bearish" in desc

    def test_boundary_extreme_fear(self) -> None:
        signal, _ = classify_pcr_signal(PCR_EXTREME_FEAR)
        assert signal == "extreme_fear"

    def test_boundary_high_fear(self) -> None:
        signal, _ = classify_pcr_signal(PCR_HIGH_FEAR)
        assert signal == "fear"

    def test_boundary_extreme_greed(self) -> None:
        signal, _ = classify_pcr_signal(PCR_EXTREME_GREED)
        assert signal == "extreme_greed"

    def test_boundary_high_greed(self) -> None:
        signal, _ = classify_pcr_signal(PCR_HIGH_GREED)
        assert signal == "greed"

    def test_zero_pcr(self) -> None:
        signal, _ = classify_pcr_signal(0.0)
        assert signal == "extreme_greed"


class TestPCRStrikePoint:
    def test_frozen(self) -> None:
        p = PCRStrikePoint(
            strike=100.0,
            call_volume=500,
            put_volume=400,
            call_oi=1000,
            put_oi=800,
            pcr_volume=0.8,
            pcr_oi=0.8,
            moneyness=1.0,
        )
        assert p.strike == 100.0
        assert p.pcr_volume == 0.8
        with pytest.raises(AttributeError):
            p.strike = 200.0  # type: ignore[misc]

    def test_slots(self) -> None:
        p = PCRStrikePoint(
            strike=100.0,
            call_volume=0,
            put_volume=0,
            call_oi=0,
            put_oi=0,
            pcr_volume=0.0,
            pcr_oi=0.0,
            moneyness=1.0,
        )
        assert not hasattr(p, "__dict__")


class TestPCRTermPoint:
    def test_frozen(self) -> None:
        t = PCRTermPoint(
            expiration="2025-04-18",
            dte_days=14,
            call_volume=1000,
            put_volume=800,
            call_oi=5000,
            put_oi=4000,
            pcr_volume=0.8,
            pcr_oi=0.8,
        )
        assert t.dte_days == 14
        with pytest.raises(AttributeError):
            t.dte_days = 30  # type: ignore[misc]


class TestPutCallRatioResult:
    def test_defaults(self) -> None:
        r = PutCallRatioResult(symbol="TEST")
        assert r.symbol == "TEST"
        assert r.spot_price == 0.0
        assert r.pcr_volume == 0.0
        assert r.pcr_oi == 0.0
        assert r.signal == "neutral"
        assert r.strike_points == []
        assert r.term_structure == []
        assert r.error is None

    def test_mutable(self) -> None:
        r = PutCallRatioResult(symbol="TEST")
        r.pcr_volume = 1.5
        assert r.pcr_volume == 1.5

    def test_error_field(self) -> None:
        r = PutCallRatioResult(symbol="BAD", error="No data")
        assert r.error == "No data"


class TestExtractStrikePoints:
    def _make_df(self, data: list[dict[str, float | int]]) -> pd.DataFrame:
        return pd.DataFrame(data)

    def test_basic_extraction(self) -> None:
        calls = self._make_df(
            [
                {"strike": 90.0, "volume": 100, "openInterest": 500},
                {"strike": 100.0, "volume": 200, "openInterest": 1000},
                {"strike": 110.0, "volume": 150, "openInterest": 800},
            ]
        )
        puts = self._make_df(
            [
                {"strike": 90.0, "volume": 300, "openInterest": 600},
                {"strike": 100.0, "volume": 250, "openInterest": 900},
                {"strike": 110.0, "volume": 50, "openInterest": 400},
            ]
        )
        points = _extract_strike_points(calls, puts, spot=100.0)
        assert len(points) == 3
        atm = [p for p in points if p.strike == 100.0][0]
        assert atm.call_volume == 200
        assert atm.put_volume == 250
        assert atm.pcr_volume == _safe_ratio(250, 200)

    def test_filters_out_of_range(self) -> None:
        calls = self._make_df(
            [
                {"strike": 50.0, "volume": 100, "openInterest": 500},
                {"strike": 100.0, "volume": 200, "openInterest": 1000},
                {"strike": 200.0, "volume": 100, "openInterest": 500},
            ]
        )
        puts = self._make_df(
            [
                {"strike": 100.0, "volume": 150, "openInterest": 600},
            ]
        )
        points = _extract_strike_points(calls, puts, spot=100.0)
        strikes = [p.strike for p in points]
        assert 50.0 not in strikes
        assert 200.0 not in strikes
        assert 100.0 in strikes

    def test_empty_calls(self) -> None:
        puts = self._make_df(
            [
                {"strike": 100.0, "volume": 150, "openInterest": 600},
            ]
        )
        points = _extract_strike_points(pd.DataFrame(), puts, spot=100.0)
        assert len(points) == 1
        assert points[0].call_volume == 0

    def test_empty_both(self) -> None:
        points = _extract_strike_points(pd.DataFrame(), pd.DataFrame(), spot=100.0)
        assert points == []

    def test_nan_handling(self) -> None:
        calls = self._make_df(
            [
                {"strike": 100.0, "volume": float("nan"), "openInterest": float("nan")},
            ]
        )
        puts = self._make_df(
            [
                {"strike": 100.0, "volume": 50, "openInterest": 200},
            ]
        )
        points = _extract_strike_points(calls, puts, spot=100.0)
        assert len(points) == 1
        assert points[0].call_volume == 0
        assert points[0].call_oi == 0

    def test_moneyness(self) -> None:
        calls = self._make_df(
            [
                {"strike": 110.0, "volume": 100, "openInterest": 500},
            ]
        )
        points = _extract_strike_points(calls, pd.DataFrame(), spot=100.0)
        assert len(points) == 1
        assert points[0].moneyness == 1.1


class TestComputeAtmRatio:
    def _make_df(self, data: list[dict[str, float | int]]) -> pd.DataFrame:
        return pd.DataFrame(data)

    def test_basic_atm(self) -> None:
        calls = self._make_df(
            [
                {"strike": 95.0, "volume": 100, "openInterest": 500},
                {"strike": 100.0, "volume": 200, "openInterest": 1000},
                {"strike": 105.0, "volume": 100, "openInterest": 500},
            ]
        )
        puts = self._make_df(
            [
                {"strike": 95.0, "volume": 150, "openInterest": 600},
                {"strike": 100.0, "volume": 250, "openInterest": 900},
                {"strike": 105.0, "volume": 50, "openInterest": 400},
            ]
        )
        vol_ratio, oi_ratio = _compute_atm_ratio(calls, puts, spot=100.0)
        assert vol_ratio > 0
        assert oi_ratio > 0

    def test_empty_df(self) -> None:
        vol_ratio, oi_ratio = _compute_atm_ratio(pd.DataFrame(), pd.DataFrame(), spot=100.0)
        assert vol_ratio == 0.0
        assert oi_ratio == 0.0

    def test_out_of_range_excluded(self) -> None:
        calls = self._make_df(
            [
                {"strike": 50.0, "volume": 1000, "openInterest": 5000},
            ]
        )
        puts = self._make_df(
            [
                {"strike": 50.0, "volume": 500, "openInterest": 2500},
            ]
        )
        vol_ratio, oi_ratio = _compute_atm_ratio(calls, puts, spot=100.0)
        assert vol_ratio == 0.0
        assert oi_ratio == 0.0

    def test_weighting_favours_atm(self) -> None:
        calls = self._make_df(
            [
                {"strike": 100.0, "volume": 100, "openInterest": 100},
                {"strike": 109.0, "volume": 100, "openInterest": 100},
            ]
        )
        puts = self._make_df(
            [
                {"strike": 100.0, "volume": 200, "openInterest": 200},
                {"strike": 109.0, "volume": 50, "openInterest": 50},
            ]
        )
        vol_ratio, _ = _compute_atm_ratio(calls, puts, spot=100.0)
        assert vol_ratio > 1.0


class TestThresholdConstants:
    def test_ordering(self) -> None:
        assert PCR_EXTREME_GREED < PCR_HIGH_GREED < PCR_HIGH_FEAR < PCR_EXTREME_FEAR

    def test_reasonable_ranges(self) -> None:
        assert 0.0 < PCR_EXTREME_GREED < 1.0
        assert 0.0 < PCR_HIGH_GREED < 1.0
        assert PCR_HIGH_FEAR >= 0.8
        assert PCR_EXTREME_FEAR >= 1.0
