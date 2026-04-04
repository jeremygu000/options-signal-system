from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from app.config import settings
from app.data_provider import get_daily
from app.ml.regime_classifier import RegimeClassifier
from app.ml.signal_scorer import SignalScorer

logger = logging.getLogger(__name__)

MODELS_DIR = settings.parquet_dir / "models"
PIPELINE_STATUS_PATH = MODELS_DIR / "pipeline_status.json"


@dataclass
class TrainingStatus:
    last_trained: str | None = None
    regime_metrics: dict[str, object] = field(default_factory=dict)
    scorer_metrics: dict[str, object] = field(default_factory=dict)
    symbols_trained: list[str] = field(default_factory=list)
    error: str | None = None


def _save_status(status: TrainingStatus) -> None:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    data = {
        "last_trained": status.last_trained,
        "regime_metrics": status.regime_metrics,
        "scorer_metrics": status.scorer_metrics,
        "symbols_trained": status.symbols_trained,
        "error": status.error,
    }
    PIPELINE_STATUS_PATH.write_text(json.dumps(data, indent=2, default=str))


def load_status() -> TrainingStatus:
    if not PIPELINE_STATUS_PATH.exists():
        return TrainingStatus()
    try:
        data = json.loads(PIPELINE_STATUS_PATH.read_text())
        return TrainingStatus(
            last_trained=data.get("last_trained"),
            regime_metrics=data.get("regime_metrics", {}),
            scorer_metrics=data.get("scorer_metrics", {}),
            symbols_trained=data.get("symbols_trained", []),
            error=data.get("error"),
        )
    except Exception:
        return TrainingStatus()


def run_training_pipeline(
    regime_classifier: RegimeClassifier,
    signal_scorer: SignalScorer,
    lookback_days: int = 365,
    symbols: list[str] | None = None,
) -> TrainingStatus:
    """Execute full training pipeline: regime HMM + signal scorer.

    1. Fetch QQQ + VIX data → train regime HMM
    2. For each symbol, fetch daily data → train signal scorer on first symbol
       with sufficient data (features are symbol-agnostic)
    3. Save models + metadata
    """
    status = TrainingStatus()

    try:
        # ── Phase 1: Regime classifier ───────────────────────────────
        qqq_daily = get_daily(settings.market_index, lookback_days)
        vix_daily = get_daily(settings.volatility_index, lookback_days)

        if qqq_daily.empty or vix_daily.empty:
            status.error = "Cannot fetch QQQ/VIX data for regime training"
            _save_status(status)
            return status

        regime_metrics = regime_classifier.train(qqq_daily, vix_daily)
        regime_classifier.save()
        status.regime_metrics = regime_metrics

        # ── Phase 2: Signal scorer ───────────────────────────────────
        # Train on the symbol with the most data
        trained_on: str | None = None
        for sym in symbols or []:
            daily = get_daily(sym, lookback_days)
            if len(daily) >= 200:
                scorer_metrics = signal_scorer.train(daily, horizon=5)
                signal_scorer.save()
                status.scorer_metrics = scorer_metrics
                trained_on = sym
                break

        if trained_on is None:
            status.error = "No symbol has enough data (>= 200 rows) for scorer training"
            _save_status(status)
            return status

        status.symbols_trained = [trained_on]
        status.last_trained = datetime.now(UTC).isoformat()
        _save_status(status)

        logger.info("Training pipeline complete. Regime on QQQ+VIX, scorer on %s", trained_on)
        return status

    except Exception as exc:
        logger.exception("Training pipeline failed")
        status.error = str(exc)[:500]
        _save_status(status)
        return status
