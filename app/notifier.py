"""Multi-channel notifier — Telegram, WeChat (企业微信), extensible.

Channel 设计:
- BaseNotifier: 抽象基类
- TelegramNotifier: Telegram Bot API
- WeChatNotifier: 企业微信 Webhook
- CompositeNotifier: 聚合多个 channel，统一发送

所有 channel 在配置缺失时静默禁用，不报错。
"""

from __future__ import annotations

import abc
import logging

import httpx
import requests

from app.config import settings

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"
DEFAULT_TIMEOUT = 10


class BaseNotifier(abc.ABC):

    @abc.abstractmethod
    def is_enabled(self) -> bool: ...

    @abc.abstractmethod
    def send(self, message: str) -> bool: ...

    @abc.abstractmethod
    async def send_async(self, message: str) -> bool: ...

    @property
    @abc.abstractmethod
    def channel_name(self) -> str: ...


class TelegramNotifier(BaseNotifier):

    def __init__(self, token: str = "", chat_id: str = "") -> None:
        self._token = token or settings.telegram_bot_token.get_secret_value()
        self._chat_id = chat_id or settings.telegram_chat_id.get_secret_value()

    @property
    def channel_name(self) -> str:
        return "Telegram"

    def is_enabled(self) -> bool:
        return bool(self._token and self._chat_id)

    def _build_payload(self, message: str) -> tuple[str, dict[str, str]]:
        url = TELEGRAM_API.format(token=self._token)
        payload = {"chat_id": self._chat_id, "text": message, "parse_mode": "HTML"}
        return url, payload

    def send(self, message: str) -> bool:
        if not self.is_enabled():
            return False
        url, payload = self._build_payload(message)
        try:
            resp = requests.post(url, json=payload, timeout=DEFAULT_TIMEOUT)
            if resp.ok:
                logger.info("Telegram 通知发送成功")
                return True
            logger.warning("Telegram 发送失败: %s %s", resp.status_code, resp.text)
            return False
        except Exception:
            logger.exception("Telegram 发送异常")
            return False

    async def send_async(self, message: str) -> bool:
        if not self.is_enabled():
            return False
        url, payload = self._build_payload(message)
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(url, json=payload, timeout=DEFAULT_TIMEOUT)
            if resp.is_success:
                logger.info("Telegram 通知发送成功")
                return True
            logger.warning("Telegram 发送失败: %s %s", resp.status_code, resp.text)
            return False
        except Exception:
            logger.exception("Telegram 发送异常")
            return False


class WeChatNotifier(BaseNotifier):
    """企业微信群机器人 Webhook 通知。

    配置: WECHAT_WEBHOOK_URL 环境变量。
    文档: https://developer.work.weixin.qq.com/document/path/91770
    """

    def __init__(self, webhook_url: str = "") -> None:
        self._webhook_url = webhook_url or settings.wechat_webhook_url.get_secret_value()

    @property
    def channel_name(self) -> str:
        return "WeChat"

    def is_enabled(self) -> bool:
        return bool(self._webhook_url)

    @staticmethod
    def _build_payload(message: str) -> dict[str, object]:
        return {"msgtype": "text", "text": {"content": message}}

    def _check_response(self, data: dict[str, object]) -> bool:
        if data.get("errcode", 0) == 0:
            logger.info("WeChat 通知发送成功")
            return True
        logger.warning("WeChat 发送失败: %s", data)
        return False

    def send(self, message: str) -> bool:
        if not self.is_enabled():
            return False
        payload = self._build_payload(message)
        try:
            resp = requests.post(self._webhook_url, json=payload, timeout=DEFAULT_TIMEOUT)
            if resp.ok:
                return self._check_response(resp.json())
            logger.warning("WeChat HTTP 错误: %s %s", resp.status_code, resp.text)
            return False
        except Exception:
            logger.exception("WeChat 发送异常")
            return False

    async def send_async(self, message: str) -> bool:
        if not self.is_enabled():
            return False
        payload = self._build_payload(message)
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(self._webhook_url, json=payload, timeout=DEFAULT_TIMEOUT)
            if resp.is_success:
                return self._check_response(resp.json())
            logger.warning("WeChat HTTP 错误: %s %s", resp.status_code, resp.text)
            return False
        except Exception:
            logger.exception("WeChat 发送异常")
            return False


class CompositeNotifier(BaseNotifier):
    """聚合多个通知 channel，统一调用。"""

    def __init__(self, notifiers: list[BaseNotifier] | None = None) -> None:
        self._notifiers = notifiers or []

    @property
    def channel_name(self) -> str:
        enabled = [n.channel_name for n in self._notifiers if n.is_enabled()]
        return ", ".join(enabled) if enabled else "None"

    def is_enabled(self) -> bool:
        return any(n.is_enabled() for n in self._notifiers)

    def send(self, message: str) -> bool:
        if not self.is_enabled():
            logger.debug("所有通知渠道均未配置，跳过发送")
            return False
        success = False
        for notifier in self._notifiers:
            if notifier.is_enabled():
                try:
                    if notifier.send(message):
                        success = True
                except Exception:
                    logger.exception("%s 通知发送失败", notifier.channel_name)
        return success

    async def send_async(self, message: str) -> bool:
        if not self.is_enabled():
            logger.debug("所有通知渠道均未配置，跳过发送")
            return False
        success = False
        for notifier in self._notifiers:
            if notifier.is_enabled():
                try:
                    if await notifier.send_async(message):
                        success = True
                except Exception:
                    logger.exception("%s 通知发送失败", notifier.channel_name)
        return success


def create_notifier() -> CompositeNotifier:
    """Factory: 创建包含所有已配置 channel 的 CompositeNotifier。"""
    return CompositeNotifier(
        [
            TelegramNotifier(),
            WeChatNotifier(),
        ]
    )
