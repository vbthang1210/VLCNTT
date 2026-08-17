from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock

try:
    import paho.mqtt.client as mqtt
except ImportError:  # pragma: no cover - exercised only when dependency is absent
    mqtt = None


ALLOWED_STATUSES = {
    "ONLINE",
    "OFFLINE",
    "IDLE",
    "BUFFERING",
    "PLAYING",
    "PAUSED",
    "STOPPED",
    "ERROR",
}


@dataclass
class DeviceState:
    device_id: str
    status: str = "OFFLINE"
    request_id: str | None = None
    audio_id: str | None = None
    updated_at: str | None = None
    error: dict | None = None
    last_event: dict | None = None


class DeviceStateStore:
    def __init__(self):
        self._states: dict[str, DeviceState] = {}
        self._request_order: dict[str, str] = {}
        self._lock = Lock()

    def get(self, device_id: str) -> DeviceState:
        with self._lock:
            return self._states.setdefault(device_id, DeviceState(device_id))

    def update(self, payload: dict) -> DeviceState | None:
        device_id = payload.get("device_id")
        status = payload.get("status")
        if not isinstance(device_id, str) or status not in ALLOWED_STATUSES:
            return None
        request_id = payload.get("request_id")
        with self._lock:
            current_request = self._request_order.get(device_id)
            if request_id and current_request and request_id != current_request:
                return self._states.get(device_id)
            state = self._states.setdefault(device_id, DeviceState(device_id))
            state.status = status
            state.request_id = request_id or state.request_id
            state.audio_id = payload.get("audio_id", state.audio_id)
            state.error = payload.get("error")
            state.updated_at = datetime.now(timezone.utc).isoformat()
            return state

    def record_event(self, payload: dict) -> DeviceState | None:
        device_id = payload.get("device_id")
        if not isinstance(device_id, str):
            return None
        request_id = payload.get("request_id")
        with self._lock:
            current_request = self._request_order.get(device_id)
            if request_id and current_request and request_id != current_request:
                return self._states.get(device_id)
            state = self._states.setdefault(device_id, DeviceState(device_id))
            state.last_event = dict(payload)
            state.updated_at = datetime.now(timezone.utc).isoformat()
            return state

    def set_current_request(self, device_id: str, request_id: str) -> None:
        with self._lock:
            self._request_order[device_id] = request_id
            state = self._states.setdefault(device_id, DeviceState(device_id))
            state.request_id = request_id

    @staticmethod
    def as_dict(state: DeviceState) -> dict:
        return {
            "device_id": state.device_id,
            "status": state.status,
            "request_id": state.request_id,
            "audio_id": state.audio_id,
            "updated_at": state.updated_at,
            "error": state.error,
            "last_event": state.last_event,
        }


class MqttService:
    def __init__(self, settings, state_store: DeviceStateStore, notification_service=None, cloud_service=None):
        self.settings = settings
        self.state_store = state_store
        self.notification_service = notification_service
        self.cloud_service = cloud_service
        self.client = None
        self._connected = False

    def start(self) -> None:
        if not self.settings.mqtt_enabled or mqtt is None:
            return
        try:
            self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, client_id="backend")
        except AttributeError:
            self.client = mqtt.Client(client_id="backend")
        if self.settings.mqtt_username:
            self.client.username_pw_set(self.settings.mqtt_username, self.settings.mqtt_password or "")
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        self.client.on_log = self._on_log
        try:
            self.client.connect(self.settings.mqtt_host, self.settings.mqtt_port, 10)
            self.client.loop_start()
        except OSError:
            self._connected = False

    def _on_connect(self, client, userdata, flags, rc):
        self._connected = rc == 0
        if self._connected:
            client.subscribe("esp32/+/status", qos=1)
            client.subscribe("esp32/+/event", qos=1)
            client.subscribe("esp32/+/error", qos=1)

    def _on_disconnect(self, client, userdata, rc):
        self._connected = False

    def _on_log(self, client, userdata, level, buf):
        # Keep broker diagnostics out of normal application output.
        return

    def _on_message(self, client, userdata, message):
        try:
            payload = json.loads(message.payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return
        if not isinstance(payload, dict):
            return
        parts = message.topic.split("/")
        if len(parts) == 3 and parts[0] == "esp32" and parts[2] == "event":
            self.state_store.record_event(payload)
            self._notify(payload)
            return
        if len(parts) == 3 and parts[0] == "esp32" and parts[2] == "error":
            payload = dict(payload)
            payload["status"] = "ERROR"
            payload["error"] = {
                "code": payload.get("error_code", "DEVICE_ERROR"),
                "message": payload.get("message", "Device reported an error"),
            }
        self.state_store.update(payload)
        self._persist_status(payload)
        if payload.get("status") in {"ERROR", "OFFLINE"}:
            self._notify(payload)

    def _persist_status(self, payload: dict) -> None:
        if self.cloud_service is None:
            return
        try:
            self.cloud_service.save_status(payload)
        except Exception:
            # Cloud persistence failure must not prevent device state ingestion.
            return

    def _notify(self, payload: dict) -> None:
        if self.notification_service is None:
            return
        try:
            self.notification_service.notify(payload)
        except Exception:
            # Notification failure must not prevent MQTT state ingestion.
            return

    def is_connected(self) -> bool:
        return self._connected

    def publish_command(self, device_id: str, payload: dict) -> bool:
        if not self.settings.mqtt_enabled:
            return False
        if self.client is None or not self._connected:
            return False
        topic = f"esp32/{device_id}/command"
        result = self.client.publish(topic, json.dumps(payload), qos=1, retain=False)
        return result.rc == mqtt.MQTT_ERR_SUCCESS

    def stop(self) -> None:
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
            self._connected = False
