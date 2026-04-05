"""Tests for ML modules: features, regime classifier, signal scorer, pipeline, endpoints."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.server import app

# ── Helpers ──────────────────────────────────────────────────────────


def _make_daily(n: int = 250, base: float = 100.0) -> pd.DataFrame:
    """Generate realistic OHLCV DataFrame with DatetimeIndex (enough for ML)."""
    rng = np.random.default_rng(42)
    dates = pd.bdate_range(end=pd.Timestamp.now(), periods=n + 5)[-n:]
    closes = base + np.cumsum(rng.normal(0, 0.5, n))
    highs = closes + rng.uniform(0.5, 2.0, n)
    lows = closes - rng.uniform(0.5, 2.0, n)
    opens = closes + rng.normal(0, 0.3, n)
    volumes = rng.integers(1_000_000, 10_000_000, n)
    return pd.DataFrame(
        {"Open": opens, "High": highs, "Low": lows, "Close": closes, "Volume": volumes},
        index=dates,
    )


def _make_short_daily(n: int = 30) -> pd.DataFrame:
    """Generate short OHLCV DataFrame (insufficient for features)."""
    return _make_daily(n=n)


@pytest.fixture()
def client() -> TestClient:  # type: ignore[misc]
    with TestClient(app) as c:
        yield c  # type: ignore[misc]


# ── Feature Engineering ──────────────────────────────────────────────


class TestComputeFeatures:
    def test_returns_dataframe_with_features(self) -> None:
        from app.ml.features import compute_features

        daily = _make_daily(250)
        result = compute_features(daily)

        assert isinstance(result, pd.DataFrame)
        assert not result.empty
        assert len(result) > 0

    def test_feature_count(self) -> None:
        from app.ml.features import compute_features

        daily = _make_daily(250)
        result = compute_features(daily)

        assert result.shape[1] >= 25

    def test_expected_feature_names(self) -> None:
        from app.ml.features import compute_features

        daily = _make_daily(250)
        result = compute_features(daily)
        cols = set(result.columns)

        # Returns
        assert "ret_1d" in cols
        assert "ret_5d" in cols
        assert "ret_10d" in cols
        assert "ret_20d" in cols
        assert "log_ret_1d" in cols

        # Volatility
        assert "vol_5d" in cols
        assert "vol_20d" in cols
        assert "vol_60d" in cols
        assert "vol_ratio_5_20" in cols
        assert "atr_14" in cols
        assert "atr_pct" in cols
        assert "parkinson_vol_20" in cols

        # Momentum
        assert "rsi_14" in cols
        assert "macd" in cols
        assert "macd_signal" in cols
        assert "macd_hist" in cols

        # Trend
        assert "sma_5_dist" in cols
        assert "sma_50_dist" in cols
        assert "ema_5_20_diff" in cols
        assert "range_pos_20" in cols

        # Volume
        assert "vol_ratio" in cols
        assert "obv_pct_change_5" in cols

    def test_no_nan_in_result(self) -> None:
        from app.ml.features import compute_features

        daily = _make_daily(250)
        result = compute_features(daily)

        assert not result.isna().any().any(), "Features should not contain NaN after dropna"

    def test_shift_prevents_lookahead(self) -> None:
        from app.ml.features import compute_features

        daily = _make_daily(250)
        result = compute_features(daily)

        # Features should be shifted by 1 day, so the last index in features
        # should be at most the second-to-last date in daily
        assert result.index[-1] <= daily.index[-1]

    def test_empty_input(self) -> None:
        from app.ml.features import compute_features

        result = compute_features(pd.DataFrame())
        assert result.empty

    def test_insufficient_data(self) -> None:
        from app.ml.features import compute_features

        daily = _make_short_daily(30)
        result = compute_features(daily)
        assert result.empty


class TestComputeLabels:
    def test_binary_labels(self) -> None:
        from app.ml.features import compute_labels

        daily = _make_daily(250)
        labels = compute_labels(daily, horizon=5)

        assert isinstance(labels, pd.Series)
        # Only 0.0 or 1.0 values (plus NaN for tail)
        valid = labels.dropna()
        assert set(valid.unique()).issubset({0.0, 1.0})

    def test_last_horizon_rows_are_zero(self) -> None:
        from app.ml.features import compute_labels

        daily = _make_daily(100)
        labels = compute_labels(daily, horizon=5)

        # Last 5 rows have NaN forward return → (NaN > 0) = False → 0.0
        assert (labels.iloc[-5:] == 0.0).all()

    def test_custom_threshold(self) -> None:
        from app.ml.features import compute_labels

        daily = _make_daily(250)
        labels_zero = compute_labels(daily, threshold=0.0)
        labels_high = compute_labels(daily, threshold=0.10)

        # Higher threshold should yield fewer positives
        valid_zero = labels_zero.dropna()
        valid_high = labels_high.dropna()
        assert valid_high.sum() <= valid_zero.sum()


# ── Regime Classifier ────────────────────────────────────────────────


class TestRegimeClassifier:
    def test_init_not_trained(self) -> None:
        from app.ml.regime_classifier import RegimeClassifier

        clf = RegimeClassifier()
        assert not clf.is_trained
        assert clf.model is None

    def test_train_and_predict(self) -> None:
        from app.ml.regime_classifier import RegimeClassifier

        clf = RegimeClassifier()
        qqq = _make_daily(300)
        vix = _make_daily(300, base=20.0)

        metrics = clf.train(qqq, vix)

        assert clf.is_trained
        assert "n_samples" in metrics
        assert "score" in metrics
        assert "state_labels" in metrics

        # Predict
        pred = clf.predict(qqq, vix)
        assert pred.regime in ("risk_on", "neutral", "risk_off")
        assert pred.source == "ml"
        assert isinstance(pred.probabilities, dict)
        assert abs(sum(pred.probabilities.values()) - 1.0) < 0.01
        assert isinstance(pred.state, int)

    def test_train_insufficient_data(self) -> None:
        from app.ml.regime_classifier import RegimeClassifier

        clf = RegimeClassifier()
        qqq = _make_daily(50)
        vix = _make_daily(50, base=20.0)

        with pytest.raises(ValueError, match="Insufficient data"):
            clf.train(qqq, vix)

    def test_predict_without_training_raises(self) -> None:
        from app.ml.regime_classifier import RegimeClassifier

        clf = RegimeClassifier()
        qqq = _make_daily(100)
        vix = _make_daily(100, base=20.0)

        with pytest.raises(RuntimeError, match="not trained"):
            clf.predict(qqq, vix)

    def test_save_and_load(self, tmp_path: object) -> None:
        from app.ml.regime_classifier import RegimeClassifier

        clf = RegimeClassifier()
        qqq = _make_daily(300)
        vix = _make_daily(300, base=20.0)
        clf.train(qqq, vix)

        with (
            patch("app.ml.regime_classifier.MODELS_DIR", tmp_path),
            patch("app.ml.regime_classifier.REGIME_MODEL_PATH", tmp_path / "regime_hmm.joblib"),  # type: ignore[operator]
            patch("app.ml.regime_classifier.REGIME_META_PATH", tmp_path / "regime_hmm_meta.json"),  # type: ignore[operator]
        ):
            saved = clf.save()
            assert saved.exists()

            # Load into new instance
            clf2 = RegimeClassifier()
            loaded = clf2.load()
            assert loaded is True
            assert clf2.is_trained

            # Should produce same prediction
            pred1 = clf.predict(qqq, vix)
            pred2 = clf2.predict(qqq, vix)
            assert pred1.regime == pred2.regime

    def test_load_nonexistent_returns_false(self, tmp_path: object) -> None:
        from app.ml.regime_classifier import RegimeClassifier

        clf = RegimeClassifier()
        with patch("app.ml.regime_classifier.REGIME_MODEL_PATH", tmp_path / "nonexistent.joblib"):  # type: ignore[operator]
            assert clf.load() is False
            assert not clf.is_trained


# ── Signal Scorer ────────────────────────────────────────────────────


class TestSignalScorer:
    def test_init_not_trained(self) -> None:
        from app.ml.signal_scorer import SignalScorer

        scorer = SignalScorer()
        assert not scorer.is_trained

    def test_train_and_predict(self) -> None:
        from app.ml.signal_scorer import SignalScorer

        scorer = SignalScorer()
        daily = _make_daily(300)

        metrics = scorer.train(daily, horizon=5)

        assert scorer.is_trained
        assert "n_samples" in metrics
        assert "n_features" in metrics
        assert "val_accuracy" in metrics
        assert "positive_rate" in metrics
        assert "top_features" in metrics

        # Predict
        result = scorer.predict(daily, base_score=7, max_base_score=10)
        assert 0.0 <= result.ml_probability <= 1.0
        assert 0.0 <= result.combined_score <= 1.0
        assert isinstance(result.feature_importance, dict)

    def test_combined_score_weights(self) -> None:
        from app.ml.signal_scorer import ALPHA, BETA, SignalScorer

        scorer = SignalScorer()
        daily = _make_daily(300)
        scorer.train(daily, horizon=5)

        result = scorer.predict(daily, base_score=5, max_base_score=10)

        # combined = ALPHA * base_norm + BETA * ml_prob
        base_norm = 5.0 / 10.0
        expected = ALPHA * base_norm + BETA * result.ml_probability
        assert abs(result.combined_score - expected) < 1e-6

    def test_train_insufficient_data(self) -> None:
        from app.ml.signal_scorer import SignalScorer

        scorer = SignalScorer()
        daily = _make_daily(100)

        with pytest.raises(ValueError, match="Insufficient aligned data"):
            scorer.train(daily)

    def test_predict_without_training_raises(self) -> None:
        from app.ml.signal_scorer import SignalScorer

        scorer = SignalScorer()
        daily = _make_daily(100)

        with pytest.raises(RuntimeError, match="not trained"):
            scorer.predict(daily, base_score=5)

    def test_predict_empty_data_raises(self) -> None:
        from app.ml.signal_scorer import SignalScorer

        scorer = SignalScorer()
        daily = _make_daily(300)
        scorer.train(daily)

        with pytest.raises(ValueError, match="Insufficient data"):
            scorer.predict(pd.DataFrame(), base_score=5)

    def test_save_and_load(self, tmp_path: object) -> None:
        from app.ml.signal_scorer import SignalScorer

        scorer = SignalScorer()
        daily = _make_daily(300)
        scorer.train(daily)

        with (
            patch("app.ml.signal_scorer.MODELS_DIR", tmp_path),
            patch("app.ml.signal_scorer.SCORER_MODEL_PATH", tmp_path / "signal_scorer.joblib"),  # type: ignore[operator]
            patch("app.ml.signal_scorer.SCORER_META_PATH", tmp_path / "signal_scorer_meta.json"),  # type: ignore[operator]
        ):
            saved = scorer.save()
            assert saved.exists()

            scorer2 = SignalScorer()
            loaded = scorer2.load()
            assert loaded is True
            assert scorer2.is_trained

            result1 = scorer.predict(daily, base_score=5)
            result2 = scorer2.predict(daily, base_score=5)
            assert abs(result1.ml_probability - result2.ml_probability) < 1e-6

    def test_load_nonexistent_returns_false(self, tmp_path: object) -> None:
        from app.ml.signal_scorer import SignalScorer

        scorer = SignalScorer()
        with patch("app.ml.signal_scorer.SCORER_MODEL_PATH", tmp_path / "nonexistent.joblib"):  # type: ignore[operator]
            assert scorer.load() is False
            assert not scorer.is_trained


# ── Pipeline ─────────────────────────────────────────────────────────


class TestPipeline:
    def test_load_status_no_file(self, tmp_path: object) -> None:
        from app.ml.pipeline import load_status

        with patch("app.ml.pipeline.PIPELINE_STATUS_PATH", tmp_path / "nonexistent.json"):  # type: ignore[operator]
            status = load_status()
            assert status.last_trained is None
            assert status.error is None

    def test_load_status_from_file(self, tmp_path: object) -> None:
        from app.ml.pipeline import load_status

        status_data = {
            "last_trained": "2025-01-01T00:00:00",
            "regime_metrics": {"n_samples": 200},
            "scorer_metrics": {"n_samples": 300},
            "symbols_trained": ["QQQ"],
            "error": None,
        }
        status_file = tmp_path / "pipeline_status.json"  # type: ignore[operator]
        status_file.write_text(json.dumps(status_data))

        with patch("app.ml.pipeline.PIPELINE_STATUS_PATH", status_file):
            status = load_status()
            assert status.last_trained == "2025-01-01T00:00:00"
            assert status.symbols_trained == ["QQQ"]

    @patch("app.ml.pipeline.get_daily")
    def test_run_training_pipeline_success(self, mock_get_daily: MagicMock) -> None:
        from app.ml.pipeline import run_training_pipeline
        from app.ml.regime_classifier import RegimeClassifier
        from app.ml.signal_scorer import SignalScorer

        daily_data = _make_daily(300)
        mock_get_daily.return_value = daily_data

        regime_clf = RegimeClassifier()
        scorer = SignalScorer()

        with patch("app.ml.pipeline._save_status"):
            status = run_training_pipeline(regime_clf, scorer, lookback_days=365, symbols=["AAPL"])

        assert status.last_trained is not None
        assert status.error is None
        assert regime_clf.is_trained
        assert scorer.is_trained

    @patch("app.ml.pipeline.get_daily")
    def test_run_training_pipeline_no_data(self, mock_get_daily: MagicMock) -> None:
        from app.ml.pipeline import run_training_pipeline
        from app.ml.regime_classifier import RegimeClassifier
        from app.ml.signal_scorer import SignalScorer

        mock_get_daily.return_value = pd.DataFrame()

        regime_clf = RegimeClassifier()
        scorer = SignalScorer()

        with patch("app.ml.pipeline._save_status"):
            status = run_training_pipeline(regime_clf, scorer)

        assert status.error is not None
        assert "Cannot fetch" in status.error


# ── LLM Analyzer ─────────────────────────────────────────────────────


class TestLLMAnalyzer:
    def test_build_prompt(self) -> None:
        from app.ml.llm_analyzer import _build_analysis_prompt

        prompt = _build_analysis_prompt(
            symbol="QQQ",
            base_signal={
                "bias": "bullish",
                "level": "strong",
                "score": 8,
                "action": "buy call",
                "option_structure": "vertical",
            },
            ml_confidence=0.75,
            ml_regime="risk_on",
            feature_importance={"ret_5d": 0.15, "vol_20d": 0.12},
        )

        assert "QQQ" in prompt
        assert "bullish" in prompt
        assert "75.0%" in prompt
        assert "risk_on" in prompt
        assert "ret_5d" in prompt


# ── Server ML Endpoints ──────────────────────────────────────────────


@dataclass
class _FakeRegimePrediction:
    regime: str = "risk_on"
    probabilities: dict[str, float] | None = None
    state: int = 2
    source: str = "ml"

    def __post_init__(self) -> None:
        if self.probabilities is None:
            self.probabilities = {"risk_on": 0.7, "neutral": 0.2, "risk_off": 0.1}


@dataclass
class _FakeScoringResult:
    ml_probability: float = 0.72
    combined_score: float = 0.65
    feature_importance: dict[str, float] | None = None

    def __post_init__(self) -> None:
        if self.feature_importance is None:
            self.feature_importance = {"ret_5d": 0.15, "vol_20d": 0.12}


class _FakeRegimeClassifier:
    def __init__(self, *, trained: bool = False) -> None:
        self._trained = trained

    @property
    def is_trained(self) -> bool:
        return self._trained

    def predict(self, qqq: object, vix: object) -> _FakeRegimePrediction:
        return _FakeRegimePrediction()

    def load(self) -> bool:
        return False


class _FakeSignalScorer:
    def __init__(self, *, trained: bool = False) -> None:
        self._trained = trained

    @property
    def is_trained(self) -> bool:
        return self._trained

    def predict(self, daily: object, base_score: int, max_base_score: int = 10) -> _FakeScoringResult:
        return _FakeScoringResult()

    def load(self) -> bool:
        return False


class TestMLStatusEndpoint:
    def test_status_no_models(self, client: TestClient) -> None:
        from app.server import get_regime_classifier, get_signal_scorer

        app.dependency_overrides[get_regime_classifier] = lambda: _FakeRegimeClassifier(trained=False)
        app.dependency_overrides[get_signal_scorer] = lambda: _FakeSignalScorer(trained=False)

        try:
            with patch("app.ml.pipeline.PIPELINE_STATUS_PATH") as mock_path:
                mock_path.exists.return_value = False
                resp = client.get("/api/v1/ml/status")
                assert resp.status_code == 200
                data = resp.json()
                assert data["regime_model_available"] is False
                assert data["scorer_model_available"] is False
        finally:
            app.dependency_overrides.pop(get_regime_classifier, None)
            app.dependency_overrides.pop(get_signal_scorer, None)


class TestMLRegimeEndpoint:
    @patch("app.server.get_daily")
    @patch("app.market_regime.get_daily")
    def test_regime_fallback_to_rule_based(
        self, mock_regime_daily: MagicMock, mock_server_daily: MagicMock, client: TestClient
    ) -> None:
        daily_data = _make_daily(100)
        mock_regime_daily.side_effect = lambda symbol, days=60: daily_data
        mock_server_daily.return_value = daily_data

        from app.server import get_regime_classifier, get_regime_engine

        get_regime_engine.cache_clear()
        app.dependency_overrides[get_regime_classifier] = lambda: _FakeRegimeClassifier(trained=False)

        try:
            resp = client.get("/api/v1/ml/regime")
            assert resp.status_code == 200
            data = resp.json()
            assert data["source"] == "rule_based"
            assert data["regime"] in ("risk_on", "neutral", "risk_off")
        finally:
            app.dependency_overrides.pop(get_regime_classifier, None)

    @patch("app.server.get_daily")
    @patch("app.market_regime.get_daily")
    def test_regime_with_ml_model(
        self, mock_regime_daily: MagicMock, mock_server_daily: MagicMock, client: TestClient
    ) -> None:
        daily_data = _make_daily(100)
        mock_regime_daily.side_effect = lambda symbol, days=60: daily_data
        mock_server_daily.return_value = daily_data

        from app.server import get_regime_classifier, get_regime_engine

        get_regime_engine.cache_clear()
        app.dependency_overrides[get_regime_classifier] = lambda: _FakeRegimeClassifier(trained=True)

        try:
            resp = client.get("/api/v1/ml/regime")
            assert resp.status_code == 200
            data = resp.json()
            assert data["source"] == "ml"
            assert data["regime"] == "risk_on"
            assert "probabilities" in data
            assert data["probabilities"]["risk_on"] == pytest.approx(0.7, abs=0.01)
        finally:
            app.dependency_overrides.pop(get_regime_classifier, None)


class TestMLTrainEndpoint:
    @patch("app.server.run_training_pipeline")
    def test_train_success(self, mock_pipeline: MagicMock, client: TestClient) -> None:
        from app.ml.pipeline import TrainingStatus
        from app.server import get_regime_classifier, get_signal_scorer

        mock_status = TrainingStatus(
            last_trained="2025-01-01T00:00:00",
            regime_metrics={"n_samples": 200},
            scorer_metrics={"n_samples": 300},
            symbols_trained=["QQQ"],
        )
        mock_pipeline.return_value = mock_status

        get_regime_classifier.cache_clear()
        get_signal_scorer.cache_clear()

        resp = client.post("/api/v1/ml/train", json={"lookback_days": 365})
        assert resp.status_code == 200
        data = resp.json()
        assert data["last_trained"] == "2025-01-01T00:00:00"
        assert data["symbols_trained"] == ["QQQ"]

    def test_train_invalid_lookback(self, client: TestClient) -> None:
        resp = client.post("/api/v1/ml/train", json={"lookback_days": 50})
        assert resp.status_code == 422

        resp = client.post("/api/v1/ml/train", json={"lookback_days": 2000})
        assert resp.status_code == 422


class TestEnhancedSignalsEndpoint:
    @patch("app.server._get_watchlist_symbols", return_value=["AAPL"])
    @patch("app.server.get_daily")
    @patch("app.market_regime.get_daily")
    def test_enhanced_signals_no_ml(
        self,
        mock_regime_daily: MagicMock,
        mock_server_daily: MagicMock,
        _mock_symbols: MagicMock,
        client: TestClient,
    ) -> None:
        daily_data = _make_daily(100)
        mock_regime_daily.side_effect = lambda symbol, days=60: daily_data
        mock_server_daily.return_value = daily_data

        from app.server import get_regime_classifier, get_regime_engine, get_signal_scorer

        get_regime_engine.cache_clear()
        app.dependency_overrides[get_regime_classifier] = lambda: _FakeRegimeClassifier(trained=False)
        app.dependency_overrides[get_signal_scorer] = lambda: _FakeSignalScorer(trained=False)

        try:
            resp = client.get("/api/v1/signals/enhanced")
            assert resp.status_code == 200
            data = resp.json()
            assert isinstance(data, list)
            assert len(data) > 0
            for sig in data:
                assert "ml_confidence" in sig
                assert "ml_regime" in sig
                assert "combined_score" in sig
        finally:
            app.dependency_overrides.pop(get_regime_classifier, None)
            app.dependency_overrides.pop(get_signal_scorer, None)

    @patch("app.server._get_watchlist_symbols", return_value=["AAPL"])
    @patch("app.server.get_daily")
    @patch("app.market_regime.get_daily")
    def test_enhanced_signals_with_ml(
        self,
        mock_regime_daily: MagicMock,
        mock_server_daily: MagicMock,
        _mock_symbols: MagicMock,
        client: TestClient,
    ) -> None:
        daily_data = _make_daily(100)
        mock_regime_daily.side_effect = lambda symbol, days=60: daily_data
        mock_server_daily.return_value = daily_data

        from app.server import get_regime_classifier, get_regime_engine, get_signal_scorer

        get_regime_engine.cache_clear()
        app.dependency_overrides[get_regime_classifier] = lambda: _FakeRegimeClassifier(trained=True)
        app.dependency_overrides[get_signal_scorer] = lambda: _FakeSignalScorer(trained=True)

        try:
            resp = client.get("/api/v1/signals/enhanced")
            assert resp.status_code == 200
            data = resp.json()
            assert isinstance(data, list)
            assert len(data) > 0
            first = data[0]
            assert first["ml_confidence"] == pytest.approx(0.72, abs=0.01)
            assert first["ml_regime"] == "risk_on"
            assert first["combined_score"] == pytest.approx(0.65, abs=0.01)
        finally:
            app.dependency_overrides.pop(get_regime_classifier, None)
            app.dependency_overrides.pop(get_signal_scorer, None)


class TestAnalyzeEndpoint:
    @patch("app.server.stream_signal_analysis")
    @patch("app.server.get_daily")
    @patch("app.market_regime.get_daily")
    def test_analyze_returns_sse(
        self,
        mock_regime_daily: MagicMock,
        mock_server_daily: MagicMock,
        mock_stream: MagicMock,
        client: TestClient,
    ) -> None:
        daily_data = _make_daily(100)
        mock_regime_daily.side_effect = lambda symbol, days=60: daily_data
        mock_server_daily.return_value = daily_data

        async def fake_stream(**kwargs: object) -> AsyncIterator[str]:
            yield '{"token": "Hello"}'
            yield '{"done": true}'

        mock_stream.return_value = fake_stream()

        from app.server import get_regime_classifier, get_regime_engine, get_signal_scorer

        get_regime_engine.cache_clear()
        app.dependency_overrides[get_regime_classifier] = lambda: _FakeRegimeClassifier(trained=False)
        app.dependency_overrides[get_signal_scorer] = lambda: _FakeSignalScorer(trained=False)

        try:
            resp = client.post("/api/v1/ml/analyze/QQQ")
            assert resp.status_code == 200
            assert resp.headers["content-type"].startswith("text/event-stream")
        finally:
            app.dependency_overrides.pop(get_regime_classifier, None)
            app.dependency_overrides.pop(get_signal_scorer, None)
