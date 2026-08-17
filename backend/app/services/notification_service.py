from __future__ import annotations

import json
from urllib import request


class NotificationNotConfigured(RuntimeError):
    pass


class NotificationService:
    """FCM HTTP v1 adapter for event notifications."""

    def __init__(
        self,
        provider=None,
        project_id: str | None = None,
        access_token: str | None = None,
        device_token: str | None = None,
        opener=None,
    ):
        self.provider = provider
        self.project_id = project_id
        self.access_token = access_token
        self.device_token = device_token
        self.opener = opener or request.urlopen

    def notify(self, event: dict) -> bool:
        if self.provider != "fcm" or not self.project_id or not self.access_token or not self.device_token:
            if self.provider:
                raise NotificationNotConfigured(
                    "FCM requires project ID, access token and device token"
                )
            return False
        data = {
            str(key): str(value)
            for key, value in event.items()
            if value is not None and isinstance(value, (str, int, float, bool))
        }
        payload = json.dumps({"message": {"token": self.device_token, "data": data}}).encode("utf-8")
        http_request = request.Request(
            f"https://fcm.googleapis.com/v1/projects/{self.project_id}/messages:send",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.access_token}",
            },
            method="POST",
        )
        with self.opener(http_request, timeout=10) as response:
            if getattr(response, "status", 200) < 200 or getattr(response, "status", 200) >= 300:
                raise RuntimeError("Notification provider request failed")
        return True
