from __future__ import annotations

import json
from urllib import request


class NotificationNotConfigured(RuntimeError):
    pass


class NotificationService:
    """Telegram Bot API adapter for device events."""

    def __init__(self, provider=None, telegram_bot_token=None, telegram_chat_id=None, opener=None):
        self.provider = provider
        self.telegram_bot_token = telegram_bot_token
        self.telegram_chat_id = telegram_chat_id
        self.opener = opener or request.urlopen

    def is_configured(self) -> bool:
        return (
            self.provider == "telegram"
            and bool(self.telegram_bot_token)
            and bool(self.telegram_chat_id)
        )

    @staticmethod
    def _notification_content(event: dict) -> dict[str, str]:
        device_id = str(event.get("device_id") or "ESP32")
        event_name = event.get("event")
        status = event.get("status")
        error_code = event.get("error_code")
        if event_name:
            title = f"ESP32 event: {event_name}"
            body = f"{device_id}: {event_name}"
        elif error_code or status == "ERROR":
            title = "ESP32 error"
            body = f"{device_id}: {error_code or 'DEVICE_ERROR'}"
        elif status == "OFFLINE":
            title = "ESP32 offline"
            body = f"{device_id} is offline"
        elif status == "ONLINE":
            title = "ESP32 online"
            body = f"{device_id} is online"
        else:
            title = "ESP32 status"
            body = f"{device_id}: {status or 'update'}"
        return {"title": title, "body": body}

    def notify(self, event: dict) -> bool:
        if not self.is_configured():
            if self.provider:
                raise NotificationNotConfigured("Telegram requires bot token and chat ID")
            return False

        content = self._notification_content(event)
        text = f"🔔 {content['title']}\n{content['body']}"[:4096]
        payload = json.dumps(
            {
                "chat_id": self.telegram_chat_id,
                "text": text,
                "disable_web_page_preview": True,
            }
        ).encode("utf-8")
        http_request = request.Request(
            f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with self.opener(http_request, timeout=10) as response:
            if getattr(response, "status", 200) < 200 or getattr(response, "status", 200) >= 300:
                raise RuntimeError("Telegram notification request failed")
            try:
                result = json.loads(response.read(64 * 1024).decode("utf-8"))
            except (AttributeError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise RuntimeError("Telegram notification response was invalid") from exc
        if not isinstance(result, dict) or result.get("ok") is not True:
            raise RuntimeError("Telegram notification provider rejected the message")
        return True
