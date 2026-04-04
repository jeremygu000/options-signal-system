"""HMM-based market regime classifier.

Uses a 3-state Gaussian HMM on market features (returns, volatility,
VIX level) to classify market regimes. Falls back to the rule-based
engine when no trained model is available.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from hmmlearn.hmm import GaussianHMM

from app.config import settings

logger = logging.getLogger(__name__)

MODELS_DIR = settings.parquet_dir / "models"
REGIME_MODEL_PATH = MODELS_DIR / "regime_hmm.joblib"
REGIME_META_PATH = MODELS_DIR / "regime_hmm_meta.json"


@dataclass
class RegimePrediction:
    regime: str  # "risk_on" | "neutral" | "risk_off"
    probabilities: dict[str, float]
    state: int
    source: str  # "ml" | "rule_based"


def _prepare_regime_features(qqq_daily: pd.DataFrame, vix_daily: pd.DataFrame) -> np.ndarray:
    """Build feature matrix for HMM from QQQ + VIX data.

    Features (all shift(1)):
      - QQQ 5d return
      - QQQ 20d realised vol
      - VIX level (normalised by 20d mean)
    """
    if qqq_daily.empty or vix_daily.empty:
        return np.array([]).reshape(0, 3)

    qqq_close = qqq_daily["Close"]
    vix_close = vix_daily["Close"]

    ret_5 = qqq_close.pct_change(5)
    vol_20 = qqq_close.pct_change().rolling(20).std() * np.sqrt(252)
    vix_norm = vix_close / vix_close.rolling(20).mean()

    combined = pd.DataFrame(
        {"ret_5": ret_5, "vol_20": vol_20, "vix_norm": vix_norm},
        index=qqq_daily.index,
    ).shift(1)

    combined = combined.reindex(qqq_daily.index).dropna()
    return combined.values.astype(np.float64)


class RegimeClassifier:
    REGIME_MAP = {0: "risk_on", 1: "neutral", 2: "risk_off"}

    def __init__(self) -> None:
        self.model: GaussianHMM | None = None
        self.state_labels: dict[int, str] = dict(self.REGIME_MAP)

    @property
    def is_trained(self) -> bool:
        return self.model is not None

    def train(self, qqq_daily: pd.DataFrame, vix_daily: pd.DataFrame) -> dict[str, object]:
        """Train the HMM on historical QQQ + VIX data."""
        X = _prepare_regime_features(qqq_daily, vix_daily)
        if len(X) < 100:
            raise ValueError(f"Insufficient data for regime training: {len(X)} rows (need >= 100)")

        hmm = GaussianHMM(
            n_components=3,
            covariance_type="full",
            n_iter=200,
            random_state=42,
        )
        hmm.fit(X)

        # Map states to regimes by mean return (highest = risk_on)
        means = hmm.means_[:, 0]  # first feature = 5d return
        order = np.argsort(means)  # ascending
        self.state_labels = {
            int(order[0]): "risk_off",
            int(order[1]): "neutral",
            int(order[2]): "risk_on",
        }

        self.model = hmm
        return {"n_samples": len(X), "score": float(hmm.score(X)), "state_labels": self.state_labels}

    def predict(self, qqq_daily: pd.DataFrame, vix_daily: pd.DataFrame) -> RegimePrediction:
        """Predict current regime from recent data."""
        if self.model is None:
            raise RuntimeError("Regime model not trained. Call train() or load() first.")

        X = _prepare_regime_features(qqq_daily, vix_daily)
        if len(X) == 0:
            raise ValueError("No valid features — check data availability")

        # Use last row for current prediction
        last_row = X[-1:].reshape(1, -1)
        state = int(self.model.predict(last_row)[0])
        proba = self.model.predict_proba(last_row)[0]

        regime = self.state_labels.get(state, "neutral")
        probabilities = {self.state_labels.get(i, f"state_{i}"): float(p) for i, p in enumerate(proba)}

        return RegimePrediction(
            regime=regime,
            probabilities=probabilities,
            state=state,
            source="ml",
        )

    def save(self) -> Path:
        if self.model is None:
            raise RuntimeError("No model to save")
        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        joblib.dump(self.model, REGIME_MODEL_PATH)
        meta = {"state_labels": {str(k): v for k, v in self.state_labels.items()}}
        REGIME_META_PATH.write_text(json.dumps(meta, indent=2))
        logger.info("Regime model saved to %s", REGIME_MODEL_PATH)
        return REGIME_MODEL_PATH

    def load(self) -> bool:
        if not REGIME_MODEL_PATH.exists():
            return False
        try:
            self.model = joblib.load(REGIME_MODEL_PATH)
            if REGIME_META_PATH.exists():
                meta = json.loads(REGIME_META_PATH.read_text())
                self.state_labels = {int(k): v for k, v in meta["state_labels"].items()}
            logger.info("Regime model loaded from %s", REGIME_MODEL_PATH)
            return True
        except Exception:
            logger.exception("Failed to load regime model")
            self.model = None
            return False
