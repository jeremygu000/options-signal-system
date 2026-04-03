from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.notifier import CompositeNotifier, TelegramNotifier, WeChatNotifier, create_notifier


class TestTelegramNotifier:
    def test_disabled_when_no_token(self) -> None:
        n = TelegramNotifier(token="", chat_id="")
        assert not n.is_enabled()
        assert not n.send("test")

    def test_enabled_when_configured(self) -> None:
        n = TelegramNotifier(token="fake-token", chat_id="fake-id")
        assert n.is_enabled()

    @patch("app.notifier.requests.post")
    def test_send_success(self, mock_post: MagicMock) -> None:
        mock_post.return_value = MagicMock(ok=True)
        n = TelegramNotifier(token="tok", chat_id="cid")
        assert n.send("hello") is True
        mock_post.assert_called_once()

    @patch("app.notifier.requests.post")
    def test_send_http_failure(self, mock_post: MagicMock) -> None:
        mock_post.return_value = MagicMock(ok=False, status_code=500, text="error")
        n = TelegramNotifier(token="tok", chat_id="cid")
        assert n.send("hello") is False

    @patch("app.notifier.requests.post", side_effect=ConnectionError("timeout"))
    def test_send_exception(self, mock_post: MagicMock) -> None:
        n = TelegramNotifier(token="tok", chat_id="cid")
        assert n.send("hello") is False

    def test_channel_name(self) -> None:
        assert TelegramNotifier(token="t", chat_id="c").channel_name == "Telegram"


class TestWeChatNotifier:
    def test_disabled_when_no_url(self) -> None:
        n = WeChatNotifier(webhook_url="")
        assert not n.is_enabled()
        assert not n.send("test")

    def test_enabled_when_configured(self) -> None:
        n = WeChatNotifier(webhook_url="https://hook.example.com")
        assert n.is_enabled()

    @patch("app.notifier.requests.post")
    def test_send_success(self, mock_post: MagicMock) -> None:
        mock_post.return_value = MagicMock(ok=True)
        mock_post.return_value.json.return_value = {"errcode": 0}
        n = WeChatNotifier(webhook_url="https://hook.example.com")
        assert n.send("hello") is True

    @patch("app.notifier.requests.post")
    def test_send_api_error(self, mock_post: MagicMock) -> None:
        mock_post.return_value = MagicMock(ok=True)
        mock_post.return_value.json.return_value = {"errcode": 40001, "errmsg": "invalid"}
        n = WeChatNotifier(webhook_url="https://hook.example.com")
        assert n.send("hello") is False

    @patch("app.notifier.requests.post")
    def test_send_http_failure(self, mock_post: MagicMock) -> None:
        mock_post.return_value = MagicMock(ok=False, status_code=500, text="err")
        n = WeChatNotifier(webhook_url="https://hook.example.com")
        assert n.send("hello") is False

    def test_channel_name(self) -> None:
        assert WeChatNotifier(webhook_url="https://x").channel_name == "WeChat"


class TestCompositeNotifier:
    def test_no_channels_is_disabled(self) -> None:
        c = CompositeNotifier([])
        assert not c.is_enabled()
        assert not c.send("test")

    def test_enabled_with_one_active(self) -> None:
        t = TelegramNotifier(token="tok", chat_id="cid")
        c = CompositeNotifier([t])
        assert c.is_enabled()

    @patch("app.notifier.requests.post")
    def test_send_dispatches_to_enabled(self, mock_post: MagicMock) -> None:
        mock_post.return_value = MagicMock(ok=True)
        t = TelegramNotifier(token="tok", chat_id="cid")
        w = WeChatNotifier(webhook_url="")
        c = CompositeNotifier([t, w])
        assert c.send("hello") is True
        mock_post.assert_called_once()

    def test_channel_name_lists_enabled(self) -> None:
        t = TelegramNotifier(token="tok", chat_id="cid")
        w = WeChatNotifier(webhook_url="https://x")
        c = CompositeNotifier([t, w])
        assert "Telegram" in c.channel_name
        assert "WeChat" in c.channel_name


class TestFactory:
    def test_create_notifier_returns_composite(self) -> None:
        n = create_notifier()
        assert isinstance(n, CompositeNotifier)
