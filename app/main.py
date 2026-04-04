"""CLI entry point — 单次运行或循环轮询。"""

from __future__ import annotations

import asyncio
import logging
import time

import typer

from app.config import settings
from app.database import get_session, init_db
from app.logging_config import setup_logging
from app.market_regime import MarketRegimeEngine
from app.models import SignalLevel
from app.notifier import create_notifier
from app.report import build_report, build_telegram_message
from app.strategy_engine import StrategyEngine
from app.utils import is_market_open
from app.watchlist import get_active_bias_map, get_active_symbols, seed_default_watchlist

logger = logging.getLogger(__name__)

cli = typer.Typer(help="期权信号系统")


def _load_watchlist_data() -> tuple[list[str], dict[str, str]]:
    async def _inner() -> tuple[list[str], dict[str, str]]:
        await init_db()
        async with get_session() as session:
            await seed_default_watchlist(session)
            symbols = await get_active_symbols(session)
            bias_map = await get_active_bias_map(session)
            return symbols, bias_map

    return asyncio.run(_inner())


def run_once(always_run: bool = False) -> None:
    if not always_run and not is_market_open():
        logger.info("非交易时段，跳过 (使用 --always-run 强制运行)")
        return

    regime_engine = MarketRegimeEngine(
        qqq_symbol=settings.market_index,
        vix_symbol=settings.volatility_index,
    )
    symbols, bias_map = _load_watchlist_data()
    strategy_engine = StrategyEngine(bias_map=bias_map)
    notifier = create_notifier()

    regime = regime_engine.evaluate()
    signals = [strategy_engine.evaluate_symbol(sym, regime) for sym in symbols]

    report = build_report(regime, signals)
    print(report)

    actionable = [s for s in signals if s.level != SignalLevel.NONE]
    if settings.strong_only:
        actionable = [s for s in actionable if s.level == SignalLevel.STRONG]

    if actionable and notifier.is_enabled():
        msg = build_telegram_message(regime, actionable)
        notifier.send(msg)
        logger.info("通知已发送至: %s", notifier.channel_name)


@cli.command()
def main(
    loop: bool = typer.Option(False, help="循环运行"),
    every_seconds: int | None = typer.Option(None, help="轮询间隔 (秒)"),
    always_run: bool = typer.Option(False, help="忽略交易时段过滤"),
) -> None:
    setup_logging()

    interval = every_seconds or settings.poll_interval

    if loop:
        logger.info("循环模式启动，间隔 %d 秒", interval)
        while True:
            try:
                run_once(always_run=always_run)
            except KeyboardInterrupt:
                logger.info("用户中断，退出")
                break
            except Exception:
                logger.exception("运行异常，%d 秒后重试", interval)
            time.sleep(interval)
    else:
        run_once(always_run=always_run)


if __name__ == "__main__":
    cli()
