"""LightGBM-based signal scoring model.

Binary classifier that predicts probability of positive 5-day forward
return. Combined with the rule-based score via weighted average:
    combined = alpha * base_normalised + beta * ml_probability
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.model_selection import TimeSeriesSplit

from app.config import settings
from app.ml.features import compute_features, compute_labels

logger = logging.getLogger(__name__)

MODELS_DIR = settings.parquet_dir / "models"
SCORER_MODEL_PATH = MODELS_DIR / "signal_scorer.joblib"
SCORER_META_PATH = MODELS_DIR / "signal_scorer_meta.json"

# Combination weights: alpha for rule-based, beta for ML
ALPHA = 0.4
BETA = 0.6


@dataclass
class ScoringResult:
    ml_probability: float
    combined_score: float
    feature_importance: dict[str, float] = field(default_factory=dict)


class SignalScorer:
    def __init__(self) -> None:
        self.model: CalibratedClassifierCV | None = None
        self.feature_names: list[str] = []
        self.train_metrics: dict[str, object] = {}

    @property
    def is_trained(self) -> bool:
        return self.model is not None

    def train(self, daily: pd.DataFrame, horizon: int = 5) -> dict[str, object]:
        """Train the signal scorer on historical daily data.

        Uses TimeSeriesSplit(n=5) cross-validation with CalibratedClassifierCV
        for reliable probability estimates.
        """
        features = compute_features(daily)
        labels = compute_labels(daily, horizon=horizon)

        # Align features and labels
        common_idx = features.index.intersection(labels.dropna().index)
        if len(common_idx) < 200:
            raise ValueError(f"Insufficient aligned data: {len(common_idx)} rows (need >= 200)")

        X = features.loc[common_idx]
        y = labels.loc[common_idx]
        self.feature_names = list(X.columns)

        # LightGBM base estimator
        base = LGBMClassifier(
            n_estimators=200,
            max_depth=5,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            min_child_samples=20,
            scale_pos_weight=float(len(y[y == 0]) / max(len(y[y == 1]), 1)),
            random_state=42,
            verbose=-1,
        )

        # Calibrate probabilities with TimeSeriesSplit
        tscv = TimeSeriesSplit(n_splits=5)
        self.model = CalibratedClassifierCV(
            estimator=base,
            cv=tscv,
            method="isotonic",
        )
        self.model.fit(X.values, y.values)

        # Compute training accuracy on last fold
        train_idx, val_idx = list(tscv.split(X))[-1]
        val_pred = self.model.predict(X.values[val_idx])
        val_acc = float(np.mean(val_pred == y.values[val_idx]))

        # Feature importance from base estimators
        importances = np.zeros(len(self.feature_names))
        for cal_est in self.model.calibrated_classifiers_:
            importances += cal_est.estimator.feature_importances_
        importances /= len(self.model.calibrated_classifiers_)

        importance_dict = dict(zip(self.feature_names, importances.tolist()))

        self.train_metrics = {
            "n_samples": len(X),
            "n_features": len(self.feature_names),
            "val_accuracy": val_acc,
            "positive_rate": float(y.mean()),
            "top_features": dict(sorted(importance_dict.items(), key=lambda x: x[1], reverse=True)[:10]),
        }

        return self.train_metrics

    def predict(self, daily: pd.DataFrame, base_score: int, max_base_score: int = 10) -> ScoringResult:
        """Score a signal using ML + rule-based combination.

        Parameters
        ----------
        daily : pd.DataFrame
            Recent daily OHLCV for the symbol (>= 60 rows).
        base_score : int
            Rule-based signal score from StrategyEngine.
        max_base_score : int
            Maximum possible rule-based score (for normalisation).
        """
        if self.model is None:
            raise RuntimeError("Signal scorer not trained. Call train() or load() first.")

        features = compute_features(daily)
        if features.empty:
            raise ValueError("Insufficient data to compute features")

        last_row = features.iloc[-1:].values
        ml_prob = float(self.model.predict_proba(last_row)[0, 1])

        # Normalise base score to [0, 1]
        base_norm = max(0.0, min(1.0, base_score / max(max_base_score, 1)))

        combined = ALPHA * base_norm + BETA * ml_prob

        # Feature importance (abbreviated)
        importance: dict[str, float] = {}
        if self.feature_names:
            importances = np.zeros(len(self.feature_names))
            for cal_est in self.model.calibrated_classifiers_:
                importances += cal_est.estimator.feature_importances_
            importances /= len(self.model.calibrated_classifiers_)
            top_n = sorted(zip(self.feature_names, importances.tolist()), key=lambda x: x[1], reverse=True)[:5]
            importance = dict(top_n)

        return ScoringResult(
            ml_probability=ml_prob,
            combined_score=combined,
            feature_importance=importance,
        )

    def save(self) -> Path:
        if self.model is None:
            raise RuntimeError("No model to save")
        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        joblib.dump(self.model, SCORER_MODEL_PATH)
        meta = {
            "feature_names": self.feature_names,
            "train_metrics": self.train_metrics,
            "alpha": ALPHA,
            "beta": BETA,
        }
        SCORER_META_PATH.write_text(json.dumps(meta, indent=2, default=str))
        logger.info("Signal scorer saved to %s", SCORER_MODEL_PATH)
        return SCORER_MODEL_PATH

    def load(self) -> bool:
        if not SCORER_MODEL_PATH.exists():
            return False
        try:
            self.model = joblib.load(SCORER_MODEL_PATH)
            if SCORER_META_PATH.exists():
                meta = json.loads(SCORER_META_PATH.read_text())
                self.feature_names = meta.get("feature_names", [])
                self.train_metrics = meta.get("train_metrics", {})
            logger.info("Signal scorer loaded from %s", SCORER_MODEL_PATH)
            return True
        except Exception:
            logger.exception("Failed to load signal scorer")
            self.model = None
            return False
