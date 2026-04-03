"""Report builder — 生成清晰的中文控制台报告。"""

from __future__ import annotations

from app.models import MarketRegimeResult, Signal, SignalLevel
from app.utils import now_ny


def build_report(regime: MarketRegimeResult, signals: list[Signal]) -> str:
    lines: list[str] = []
    now = now_ny().strftime("%Y-%m-%d %H:%M:%S")
    lines.append("=" * 60)
    lines.append(f"  期权信号系统报告  |  {now}")
    lines.append("=" * 60)

    lines.append("")
    lines.append("【大盘环境】")
    lines.append(f"  QQQ: {regime.qqq_price:.2f}  |  VIX: {regime.vix_price:.2f}")
    lines.append(f"  判定: {regime.regime.value}")
    for r in regime.reasons:
        lines.append(f"  · {r}")

    lines.append("")
    lines.append("-" * 60)

    for sig in signals:
        lines.append("")
        lines.append(_format_signal(sig))

    lines.append("")
    lines.append("=" * 60)

    # Summary
    strong = [s for s in signals if s.level == SignalLevel.STRONG]
    watch = [s for s in signals if s.level == SignalLevel.WATCH]
    if strong:
        lines.append(f"  ⚡ 强信号: {', '.join(s.symbol for s in strong)}")
    if watch:
        lines.append(f"  👀 观察中: {', '.join(s.symbol for s in watch)}")
    if not strong and not watch:
        lines.append("  ✅ 当前无交易信号")
    lines.append("=" * 60)

    return "\n".join(lines)


def _format_signal(sig: Signal) -> str:
    lines: list[str] = []

    level_icon = {"强信号": "🔴", "观察信号": "🟡", "无信号": "⚪"}
    icon = level_icon.get(sig.level.value, "")

    lines.append(f"[{sig.level.value}] {icon} {sig.symbol} | {sig.bias.value}")
    if sig.action:
        lines.append(f"  操作: {sig.action}")
    if sig.price > 0:
        lines.append(f"  现价: {sig.price:.2f}")
    if sig.trigger_price > 0 and sig.trigger_price != sig.price:
        lines.append(f"  触发位: {sig.trigger_price:.2f}")
    if sig.option_structure:
        lines.append(f"  建议结构: {sig.option_structure}")
    if sig.option_hint:
        lines.append(f"  执行提示: {sig.option_hint}")
    lines.append(f"  评分: {sig.score}")
    if sig.rationale:
        lines.append("  原因:")
        for r in sig.rationale:
            lines.append(f"    - {r}")

    return "\n".join(lines)


def build_telegram_message(regime: MarketRegimeResult, signals: list[Signal]) -> str:
    """Compact message for Telegram / WeChat notifications."""
    lines: list[str] = []
    lines.append(f"📊 期权信号 | {now_ny().strftime('%H:%M')}")
    lines.append(f"大盘: {regime.regime.value} (QQQ {regime.qqq_price:.2f}, VIX {regime.vix_price:.2f})")
    lines.append("")

    for sig in signals:
        if sig.level == SignalLevel.NONE:
            continue
        icon = "🔴" if sig.level == SignalLevel.STRONG else "🟡"
        lines.append(f"{icon} {sig.symbol} | {sig.bias.value} | {sig.level.value}")
        lines.append(f"   现价 {sig.price:.2f}")
        if sig.option_structure:
            lines.append(f"   建议: {sig.option_structure}")
        top_reasons = sig.rationale[:3]
        for r in top_reasons:
            lines.append(f"   · {r}")
        lines.append("")

    if not any(s.level != SignalLevel.NONE for s in signals):
        lines.append("当前无交易信号")

    return "\n".join(lines)
