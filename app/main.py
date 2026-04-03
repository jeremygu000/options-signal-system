"""CLI entry point — 单次运行或循环轮询。

Usage:
    python -m app.main                          # 单次运行
    python -m app.main --loop                   # 循环运行 (默认600秒)
    python -m app.main --loop --every-seconds 300
    python -m app.main --always-run             # 忽略交易时段
"""

from __future__ import annotations

import argparse
import logging
import time

from app.config import settings
from app.market_regime import MarketRegimeEngine
from app.models import SignalLevel
from app.notifier import create_notifier
from app.report import build_report, build_telegram_message
from app.strategy_engine import StrategyEngine
from app.utils import is_market_open, setup_logging

logger = logging.getLogger(__name__)


def run_once(always_run: bool = False) -> None:
    if not always_run and not is_market_open():
        logger.info("非交易时段，跳过 (使用 --always-run 强制运行)")
        return

    regime_engine = MarketRegimeEngine(
        qqq_symbol=settings.market_index,
        vix_symbol=settings.volatility_index,
    )
    strategy_engine = StrategyEngine()
    notifier = create_notifier()

    regime = regime_engine.evaluate()
    signals = [strategy_engine.evaluate_symbol(sym, regime) for sym in settings.symbols]

    report = build_report(regime, signals)
    print(report)

    actionable = [s for s in signals if s.level != SignalLevel.NONE]
    if settings.strong_only:
        actionable = [s for s in actionable if s.level == SignalLevel.STRONG]

    if actionable and notifier.is_enabled():
        msg = build_telegram_message(regime, actionable)
        notifier.send(msg)
        logger.info("通知已发送至: %s", notifier.channel_name)


def main() -> None:
    parser = argparse.ArgumentParser(description="期权信号系统")
    parser.add_argument("--loop", action="store_true", help="循环运行")
    parser.add_argument("--every-seconds", type=int, default=None, help="轮询间隔 (秒)")
    parser.add_argument("--always-run", action="store_true", help="忽略交易时段过滤")
    args = parser.parse_args()

    setup_logging()

    interval = args.every_seconds or settings.poll_interval

    if args.loop:
        logger.info("循环模式启动，间隔 %d 秒", interval)
        while True:
            try:
                run_once(always_run=args.always_run)
            except KeyboardInterrupt:
                logger.info("用户中断，退出")
                break
            except Exception:
                logger.exception("运行异常，%d 秒后重试", interval)
            time.sleep(interval)
    else:
        run_once(always_run=args.always_run)


if __name__ == "__main__":
    main()
