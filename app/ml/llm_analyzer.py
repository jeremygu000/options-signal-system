from __future__ import annotations

import json
import logging
from typing import AsyncIterator

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


def _build_analysis_prompt(
    symbol: str,
    base_signal: dict[str, object],
    ml_confidence: float,
    ml_regime: str,
    feature_importance: dict[str, float],
) -> str:
    features_text = "\n".join(f"  - {k}: {v:.4f}" for k, v in feature_importance.items())

    return (
        "You are an expert options trading analyst. "
        "Analyze the following enhanced signal and provide concise, actionable commentary. "
        "Output in bilingual format: Chinese first, then English.\n\n"
        f"## Signal for {symbol}\n"
        f"- Bias: {base_signal.get('bias', 'N/A')}\n"
        f"- Signal Level: {base_signal.get('level', 'N/A')}\n"
        f"- Rule-based Score: {base_signal.get('score', 'N/A')}\n"
        f"- ML Confidence: {ml_confidence:.1%}\n"
        f"- ML Regime: {ml_regime}\n"
        f"- Action: {base_signal.get('action', 'N/A')}\n"
        f"- Option Structure: {base_signal.get('option_structure', 'N/A')}\n\n"
        f"## Top ML Features\n{features_text}\n\n"
        "## Required Analysis\n"
        "1. Signal assessment (agree/disagree with rule-based, why?)\n"
        "2. Regime context (how does current regime affect this trade?)\n"
        "3. Risk factors to watch\n"
        "4. Specific entry/exit suggestion\n\n"
        "Keep it concise (under 300 words). Use bullet points."
    )


async def stream_signal_analysis(
    symbol: str,
    base_signal: dict[str, object],
    ml_confidence: float,
    ml_regime: str,
    feature_importance: dict[str, float],
) -> AsyncIterator[str]:
    prompt = _build_analysis_prompt(symbol, base_signal, ml_confidence, ml_regime, feature_importance)

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(connect=10.0, read=120.0, write=10.0, pool=10.0)) as client:
            async with client.stream(
                "POST",
                f"{settings.ollama_base_url}/api/generate",
                json={"model": settings.ollama_model, "prompt": prompt, "stream": True},
            ) as resp:
                if resp.status_code != 200:
                    yield f'{{"error": "Ollama returned {resp.status_code}"}}'
                    return
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    token = chunk.get("response", "")
                    if token:
                        yield json.dumps({"token": token})
                    if chunk.get("done"):
                        yield '{"done": true}'
                        return
    except httpx.ConnectError:
        yield '{"error": "Cannot connect to Ollama. Is it running?"}'
    except Exception as exc:
        yield f'{{"error": "{str(exc)[:200]}"}}'
