from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
from threading import Lock

try:
    import paho.mqtt.client as mqtt
except ImportError:  # pragma: no cover - exercised only when dependency is absent
    mqtt = None

logger = logging.getLogger(__name__)
_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9_-]{1,63}$")


def is_safe_identifier(value: object) -> bool:
    return isinstance(value, str) and _SAFE_IDENTIFIER.fullmatch(value) is not None


ALLOWED_STATUSES = {
    "ONLINE",
    "OFFLINE",
    "IDLE",
    "BUFFERING",
    "PLAYING",
    "PAUSED",
    "RECORDING",
    "STOPPED",
    "ERROR",
}


@dataclass
class DeviceState:
    device_id: str
    status: str = "OFFLINE"
    request_id: str | None = None
    audio_id: str | None = None
    recording_id: str | None = None
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
            state = self._states.setdefault(device_id, DeviceState(device_id))
            closes_current_recording = (
                status == "STOPPED"
                and request_id
                and current_request
                and request_id != current_request
                and payload.get("recording_id")
                and payload["recording_id"] == state.recording_id
            )
            if request_id and current_request and request_id != current_request:
                if not closes_current_recording:
                    return state
            effective_request_id = (
                state.request_id if closes_current_recording else request_id or state.request_id
            )
            state.status = status
            state.request_id = effective_request_id
            state.audio_id = payload.get("audio_id", state.audio_id)
            state.recording_id = payload.get("recording_id", state.recording_id)
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
            "recording_id": state.recording_id,
            "updated_at": state.updated_at,
            "error": state.error,
            "last_event": state.last_event,
        }


class MqttService:
    def __init__(
        self,
        settings,
        state_store: DeviceStateStore,
        notification_service=None,
        cloud_service=None,
        recording_service=None,
        voice_command_service=None,
    ):
        self.settings = settings
        self.state_store = state_store
        self.notification_service = notification_service
        self.cloud_service = cloud_service
        self.recording_service = recording_service
        self.voice_command_service = voice_command_service
        self._voice_executor_lock = Lock()
        self._voice_stopped = False
        self._voice_executor = None
        self._ensure_voice_executor()
        self.client = None
        self._connected = False

    def set_voice_command_service(self, service) -> None:
        with self._voice_executor_lock:
            self.voice_command_service = service
            self._ensure_voice_executor_locked()

    def _ensure_voice_executor(self) -> None:
        with self._voice_executor_lock:
            self._ensure_voice_executor_locked()

    def _ensure_voice_executor_locked(self) -> None:
        if (
            not self._voice_stopped
            and self.voice_command_service is not None
            and self._voice_executor is None
        ):
            self._voice_executor = ThreadPoolExecutor(
                max_workers=1,
                thread_name_prefix="voice-command",
            )

    def _submit_voice_record(self, record: dict) -> bool:
        with self._voice_executor_lock:
            executor = self._voice_executor
            if (
                self._voice_stopped
                or executor is None
                or self.voice_command_service is None
            ):
                return False
            try:
                executor.submit(self._process_voice_record, record)
            except RuntimeError:
                return False
            return True

    def start(self) -> None:
        with self._voice_executor_lock:
            self._voice_stopped = False
            self._ensure_voice_executor_locked()
        if not self.settings.mqtt_enabled or mqtt is None:
            return
        try:
            self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, client_id="backend")
        except AttributeError:
            self.client = mqtt.Client(client_id="backend")
        if self.settings.mqtt_username:
            self.client.username_pw_set(
                self.settings.mqtt_username,
                self.settings.mqtt_password or "",
            )
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
            client.subscribe("esp32/+/audio/#", qos=1)

    def _on_disconnect(self, client, userdata, rc):
        self._connected = False

    def _on_log(self, client, userdata, level, buf):
        # Keep broker diagnostics out of normal application output.
        return

    def _on_message(self, client, userdata, message):
        parts = message.topic.split("/")
        if len(parts) >= 4 and parts[0] == "esp32" and parts[2] == "audio":
            self._handle_audio_message(parts, message.payload)
            return
        try:
            payload = json.loads(message.payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return
        if not isinstance(payload, dict):
            return
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

    def _handle_audio_message(self, parts: list[str], payload: bytes) -> None:
        if self.recording_service is None:
            return
        device_id = parts[1]
        try:
            if parts[3] == "chunk" and len(parts) == 6:
                self.recording_service.append_chunk(
                    device_id,
                    parts[4],
                    int(parts[5]),
                    payload,
                )
                return
            if len(parts) != 4 or parts[3] not in {"start", "end"}:
                return
            body = json.loads(payload.decode("utf-8"))
            if not isinstance(body, dict):
                return
            if body.get("device_id", device_id) != device_id:
                return
            body = {**body, "device_id": device_id}
            if parts[3] == "start":
                self.recording_service.start(device_id, body)
                return
            record = self.recording_service.finish(device_id, body)
            self._persist_audio_metadata(record)
            self._notify({
                "device_id": device_id,
                "event": "RECORDING_COMPLETED",
                "recording_id": record["audio_id"],
                "audio_id": record["audio_id"],
            })
            if record.get("source") == "INMP441":
                self._submit_voice_record(record)
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError, OSError, RuntimeError):
            return

    def _process_voice_record(self, record: dict) -> None:
        try:
            result = self.voice_command_service.process(record)
            logger.info(
                "Voice command result | device=%s | audio=%s | reason=%s | published=%s",
                record.get("device_id"),
                record.get("audio_id"),
                result.reason,
                result.published,
            )
        except Exception:
            logger.exception("Voice command processing failed for %s", record.get("audio_id"))

    def _persist_audio_metadata(self, record: dict) -> None:
        if self.cloud_service is None:
            return
        try:
            self.cloud_service.save_metadata(record)
        except Exception:
            # Local Backend storage remains authoritative when Cloud is unavailable.
            return

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
        request_id = payload.get("request_id") if isinstance(payload, dict) else None
        if not is_safe_identifier(device_id) or not is_safe_identifier(request_id):
            return False
        topic = f"esp32/{device_id}/command"
        try:
            result = self.client.publish(topic, json.dumps(payload), qos=1, retain=False)
        except Exception:
            logger.exception("MQTT command publish failed | device=%s", device_id)
            return False
        if getattr(result, "rc", None) != mqtt.MQTT_ERR_SUCCESS:
            return False
        self.state_store.set_current_request(device_id, request_id)
        return True

    def stop(self) -> None:
        with self._voice_executor_lock:
            self._voice_stopped = True
            executor = self._voice_executor
            self._voice_executor = None
            if executor is not None:
                executor.shutdown(wait=True, cancel_futures=True)
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
            self._connected = False
