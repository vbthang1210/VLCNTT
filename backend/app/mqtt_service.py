from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from threading import RLock
from typing import Any

import paho.mqtt.client as mqtt

from .services.audio_stream_service import AudioStreamService

logger = logging.getLogger(__name__)


# ============================================================
# MQTT TOPICS
# ============================================================

# Existing control/status protocol
STATUS_TOPIC = "esp32/+/status"
EVENT_TOPIC = "esp32/+/event"
ERROR_TOPIC = "esp32/+/error"
COMMAND_TOPIC = "esp32/{device_id}/command"

# Audio ingestion protocol
AUDIO_START_TOPIC = "vlcntt/+/audio/start"
AUDIO_DATA_TOPIC = "vlcntt/+/audio/data"
AUDIO_END_TOPIC = "vlcntt/+/audio/end"

# New VLCNTT status namespace
VLCNTT_STATUS_TOPIC = "vlcntt/+/status"
VLCNTT_COMMAND_TOPIC = "vlcntt/{device_id}/command"


# ============================================================
# DEVICE STATE
# ============================================================


@dataclass
class DeviceState:
    device_id: str

    status: str = "OFFLINE"
    request_id: str | None = None

    error: dict[str, str] | None = None
    last_event: dict[str, Any] | None = None

    updated_at: float | None = None


class DeviceStateStore:
    """
    In-memory state store for ESP32 devices.

    This class is intentionally independent from MQTT.
    MqttService receives MQTT messages and updates this store.
    """

    def __init__(self) -> None:
        self._states: dict[str, DeviceState] = {}
        self._lock = RLock()

    # ========================================================
    # GET
    # ========================================================

    def get(self, device_id: str) -> DeviceState:
        with self._lock:
            if device_id not in self._states:
                self._states[device_id] = DeviceState(
                    device_id=device_id
                )

            return self._states[device_id]

    # ========================================================
    # CURRENT REQUEST
    # ========================================================

    def set_current_request(
        self,
        device_id: str,
        request_id: str,
    ) -> None:
        with self._lock:
            state = self.get(device_id)

            state.request_id = request_id
            state.error = None

    # ========================================================
    # UPDATE STATUS
    # ========================================================

    def update_status(
        self,
        device_id: str,
        status: str,
        request_id: str | None = None,
    ) -> bool:
        """
        Update device status.

        A stale request must not overwrite
        the currently active request.
        """

        with self._lock:
            state = self.get(device_id)

            # Ignore stale request
            if (
                request_id is not None
                and state.request_id is not None
                and request_id != state.request_id
            ):
                return False

            state.status = status

            if request_id is not None:
                state.request_id = request_id

            state.error = None

            return True

    # ========================================================
    # ERROR
    # ========================================================

    def set_error(
        self,
        device_id: str,
        error: dict[str, str],
        request_id: str | None = None,
    ) -> bool:
        with self._lock:
            state = self.get(device_id)

            # Ignore stale request
            if (
                request_id is not None
                and state.request_id is not None
                and request_id != state.request_id
            ):
                return False

            state.status = "ERROR"

            if request_id is not None:
                state.request_id = request_id

            state.error = error

            return True

    # ========================================================
    # EVENT
    # ========================================================

    def set_event(
        self,
        device_id: str,
        event: dict[str, Any],
    ) -> None:
        with self._lock:
            state = self.get(device_id)
            state.last_event = event

    # ========================================================
    # SERIALIZE
    # ========================================================

    @staticmethod
    def as_dict(
        state: DeviceState,
    ) -> dict[str, Any]:
        return asdict(state)


# ============================================================
# MQTT SERVICE
# ============================================================


class MqttService:

    def __init__(
        self,
        settings,
        device_state: DeviceStateStore,
        notification_service=None,
        cloud_service=None,
        audio_stream_service: AudioStreamService | None = None,
    ):
        self.settings = settings
        self.device_state = device_state

        self.notification_service = notification_service
        self.cloud_service = cloud_service
        self.audio_stream_service = audio_stream_service

        # Paho MQTT 2.x callback API
        self.client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2
        )

        if (
            settings.mqtt_username is not None
            and settings.mqtt_password is not None
        ):
            self.client.username_pw_set(
                settings.mqtt_username,
                settings.mqtt_password,
            )

        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect

        self._connected = False

    # ========================================================
    # START
    # ========================================================

    def start(self) -> None:
        if not self.settings.mqtt_enabled:
            logger.info("[MQTT] MQTT is disabled")
            return

        logger.info(
            "[MQTT] Connecting to %s:%s",
            self.settings.mqtt_host,
            self.settings.mqtt_port,
        )

        self.client.connect(
            self.settings.mqtt_host,
            self.settings.mqtt_port,
            60,
        )

        self.client.loop_start()

    # ========================================================
    # STOP
    # ========================================================

    def stop(self) -> None:
        if not self._connected:
            return

        self.client.loop_stop()
        self.client.disconnect()

    # ========================================================
    # CONNECTED
    # ========================================================

    def is_connected(self) -> bool:
        return self._connected

    # ========================================================
    # CONNECT CALLBACK
    # ========================================================

    def _on_connect(
        self,
        client,
        userdata,
        flags,
        reason_code,
        properties=None,
    ) -> None:
        """
        Paho MQTT Callback API v2.
        """

        if reason_code.is_failure:
            self._connected = False

            logger.error(
                "[MQTT] Connection failed | reason=%s",
                reason_code,
            )

            return

        self._connected = True

        logger.info("[MQTT] Connected")

        subscriptions = [
            # Existing control/status protocol
            (STATUS_TOPIC, 0),
            (EVENT_TOPIC, 0),
            (ERROR_TOPIC, 0),

            # VLCNTT namespace
            (VLCNTT_STATUS_TOPIC, 0),

            # Audio ingestion
            (AUDIO_START_TOPIC, 1),
            (AUDIO_DATA_TOPIC, 0),
            (AUDIO_END_TOPIC, 1),
        ]

        for topic, qos in subscriptions:
            result, _mid = client.subscribe(
                topic,
                qos=qos,
            )

            if result != mqtt.MQTT_ERR_SUCCESS:
                logger.error(
                    "[MQTT] Failed to subscribe | topic=%s | rc=%s",
                    topic,
                    result,
                )
            else:
                logger.info(
                    "[MQTT] Subscribed | topic=%s | qos=%s",
                    topic,
                    qos,
                )

        # ========================================================
        # DISCONNECT CALLBACK
        # ========================================================

    def _on_disconnect(
        self,
        client,
        userdata,
        disconnect_flags,
        reason_code,
        properties=None,
    ) -> None:

        self._connected = False

        logger.warning(
            "[MQTT] Disconnected, rc=%s",
            reason_code,
        )

    # ========================================================
    # MESSAGE CALLBACK
    # ========================================================

    def _on_message(
        self,
        client,
        userdata,
        message,
    ) -> None:

        topic = message.topic

        try:
            # ------------------------------------------------
            # DEVICE STATUS
            # ------------------------------------------------

            if (
                topic.startswith("esp32/")
                and topic.endswith("/status")
            ):
                self._handle_status(
                    topic,
                    message.payload,
                )
                return

            # ------------------------------------------------
            # DEVICE EVENT
            # ------------------------------------------------

            if (
                topic.startswith("esp32/")
                and topic.endswith("/event")
            ):
                self._handle_event(
                    topic,
                    message.payload,
                )
                return

            # ------------------------------------------------
            # DEVICE ERROR
            # ------------------------------------------------

            if (
                topic.startswith("esp32/")
                and topic.endswith("/error")
            ):
                self._handle_error(
                    topic,
                    message.payload,
                )
                return

            # ------------------------------------------------
            # AUDIO START
            # ------------------------------------------------

            if (
                topic.startswith("vlcntt/")
                and topic.endswith("/audio/start")
            ):
                self._handle_audio_start(
                    topic,
                    message.payload,
                )
                return

            # ------------------------------------------------
            # AUDIO DATA
            # ------------------------------------------------

            if (
                topic.startswith("vlcntt/")
                and topic.endswith("/audio/data")
            ):
                self._handle_audio_data(
                    topic,
                    message.payload,
                )
                return

            # ------------------------------------------------
            # AUDIO END
            # ------------------------------------------------

            if (
                topic.startswith("vlcntt/")
                and topic.endswith("/audio/end")
            ):
                self._handle_audio_end(
                    topic,
                    message.payload,
                )
                return

            logger.debug(
                "[MQTT] Ignoring topic: %s",
                topic,
            )

        except Exception:
            logger.exception(
                "[MQTT] Failed to process message: %s",
                topic,
            )

    # ========================================================
    # STATUS
    # ========================================================

    def _handle_status(
        self,
        topic: str,
        payload: bytes,
    ) -> None:

        device_id = self._extract_device_id(topic)
        data = self._decode_json(payload)

        payload_device_id = data.get("device_id")

        if (
            payload_device_id is not None
            and str(payload_device_id) != device_id
        ):
            raise ValueError(
                "Status topic device_id does not match "
                "payload device_id"
            )

        status_value = data.get("status")

        if (
            not isinstance(status_value, str)
            or not status_value
        ):
            raise ValueError(
                "MQTT status payload requires status"
            )

        request_id = data.get("request_id")

        status = {
            "device_id": device_id,
            "status": status_value,
        }

        if request_id is not None:
            status["request_id"] = request_id

        if "reason" in data:
            status["reason"] = data["reason"]

        # ----------------------------------------------------
        # Update local state
        # ----------------------------------------------------

        accepted = self.device_state.update_status(
            device_id=device_id,
            status=status_value,
            request_id=request_id,
        )

        if not accepted:
            logger.info(
                "[MQTT] Ignored stale status | device=%s",
                device_id,
            )

            return

        logger.info(
            "[MQTT] Status | device=%s | status=%s",
            device_id,
            status_value,
        )

        # ----------------------------------------------------
        # Cloud persistence
        # ----------------------------------------------------

        if self.cloud_service is not None:
            try:
                self.cloud_service.save_status(status)
            except Exception:
                logger.exception(
                    "[MQTT] Failed to persist device status"
                )

        # ----------------------------------------------------
        # Offline notification
        # ----------------------------------------------------

        if (
            status_value == "OFFLINE"
            and self.notification_service is not None
        ):
            try:
                self.notification_service.notify(status)
            except Exception:
                logger.exception(
                    "[MQTT] Failed to send OFFLINE notification"
                )

    # ========================================================
    # EVENT
    # ========================================================

    def _handle_event(
        self,
        topic: str,
        payload: bytes,
    ) -> None:

        device_id = self._extract_device_id(topic)
        data = self._decode_json(payload)

        payload_device_id = data.get("device_id")

        if (
            payload_device_id is not None
            and str(payload_device_id) != device_id
        ):
            raise ValueError(
                "Event topic device_id does not match "
                "payload device_id"
            )

        event = {
            "device_id": device_id,
            "event": data.get("event"),
        }

        if "request_id" in data:
            event["request_id"] = data["request_id"]

        # ----------------------------------------------------
        # Store event
        # ----------------------------------------------------

        self.device_state.set_event(
            device_id,
            event,
        )

        logger.info(
            "[MQTT] Event | device=%s | event=%s",
            device_id,
            event.get("event"),
        )

        # ----------------------------------------------------
        # Push notification
        # ----------------------------------------------------

        if self.notification_service is not None:
            try:
                self.notification_service.notify(event)
            except Exception:
                logger.exception(
                    "[MQTT] Failed to send event notification"
                )

    # ========================================================
    # ERROR
    # ========================================================

    def _handle_error(
        self,
        topic: str,
        payload: bytes,
    ) -> None:

        device_id = self._extract_device_id(topic)
        data = self._decode_json(payload)

        payload_device_id = data.get("device_id")

        if (
            payload_device_id is not None
            and str(payload_device_id) != device_id
        ):
            raise ValueError(
                "Error topic device_id does not match "
                "payload device_id"
            )

        error_code = data.get(
            "error_code",
            "UNKNOWN_ERROR",
        )

        error_message = data.get(
            "message",
            "Unknown device error",
        )

        if not isinstance(error_code, str):
            raise ValueError(
                "MQTT error payload requires error_code"
            )

        if not isinstance(error_message, str):
            raise ValueError(
                "MQTT error payload requires message"
            )

        request_id = data.get("request_id")

        error = {
            "code": error_code,
            "message": error_message,
        }

        accepted = self.device_state.set_error(
            device_id=device_id,
            error=error,
            request_id=request_id,
        )

        if accepted:
            logger.error(
                "[MQTT] Device error | "
                "device=%s | code=%s | message=%s",
                device_id,
                error_code,
                error_message,
            )
        else:
            logger.info(
                "[MQTT] Ignored stale error | device=%s",
                device_id,
            )

    # ========================================================
    # AUDIO START
    # ========================================================

    def _handle_audio_start(
        self,
        topic: str,
        payload: bytes,
    ) -> None:

        if self.audio_stream_service is None:
            raise RuntimeError(
                "AudioStreamService is not configured"
            )

        device_id = self._extract_device_id(topic)

        session = self.audio_stream_service.start(
            payload
        )

        if session.device_id != device_id:
            raise ValueError(
                "Audio START topic device_id does not "
                "match payload device_id"
            )

        logger.info(
            "[AUDIO] Session started | "
            "device=%s | session=%s | "
            "sample_rate=%s | channels=%s",
            session.device_id,
            session.session_id,
            session.sample_rate,
            session.channels,
        )

    # ========================================================
    # AUDIO DATA
    # ========================================================

    def _handle_audio_data(
        self,
        topic: str,
        payload: bytes,
    ) -> None:

        if self.audio_stream_service is None:
            raise RuntimeError(
                "AudioStreamService is not configured"
            )

        device_id = self._extract_device_id(topic)

        self.audio_stream_service.receive_data(
            device_id=device_id,
            payload=payload,
        )

    # ========================================================
    # AUDIO END
    # ========================================================

    def _handle_audio_end(
        self,
        topic: str,
        payload: bytes,
    ) -> None:

        if self.audio_stream_service is None:
            raise RuntimeError(
                "AudioStreamService is not configured"
            )

        device_id = self._extract_device_id(topic)

        record = self.audio_stream_service.end(
            payload
        )

        if record["device_id"] != device_id:
            raise ValueError(
                "Audio END topic device_id does not "
                "match payload device_id"
            )

        logger.info(
            "[AUDIO] Session completed | "
            "device=%s | session=%s | "
            "file=%s | duration=%.3fs",
            record["device_id"],
            record["session_id"],
            record["filename"],
            record.get("duration", 0),
        )

    # ========================================================
    # PUBLISH COMMAND
    # ========================================================

    def publish_command(
        self,
        device_id: str,
        payload: dict,
    ) -> bool:
        """
        Publish command from Python backend to ESP32.

        Topic:
            esp32/{device_id}/command

        Payload:
            JSON object.
        """

        if not self._connected:
            logger.warning(
                "[MQTT] Cannot publish command: "
                "broker disconnected"
            )
            return False

        if not device_id:
            return False

        message = dict(payload)

        message.setdefault(
            "device_id",
            device_id,
        )

        topic = COMMAND_TOPIC.format(
            device_id=device_id
        )

        try:
            info = self.client.publish(
                topic,
                json.dumps(message),
                qos=1,
            )

            if info.rc != mqtt.MQTT_ERR_SUCCESS:
                logger.error(
                    "[MQTT] Command publish failed | "
                    "device=%s | rc=%s",
                    device_id,
                    info.rc,
                )
                return False

            logger.info(
                "[COMMAND] Published | "
                "device=%s | command=%s",
                device_id,
                message.get("command"),
            )

            return True

        except Exception:
            logger.exception(
                "[MQTT] Command publish exception"
            )
            return False

    # ========================================================
    # JSON DECODER
    # ========================================================

    @staticmethod
    def _decode_json(
        payload: bytes,
    ) -> dict[str, Any]:

        try:
            data = json.loads(
                payload.decode("utf-8")
            )

        except (
            UnicodeDecodeError,
            json.JSONDecodeError,
        ) as exc:

            raise ValueError(
                "Invalid JSON MQTT payload"
            ) from exc

        if not isinstance(data, dict):
            raise ValueError(
                "MQTT JSON payload must be an object"
            )

        return data

    # ========================================================
    # DEVICE ID PARSER
    # ========================================================

    @staticmethod
    def _extract_device_id(
        topic: str,
    ) -> str:

        parts = topic.split("/")

        # -----------------------------------------------
        # esp32/{device_id}/{type}
        # -----------------------------------------------

        if (
            len(parts) == 3
            and parts[0] == "esp32"
        ):
            return parts[1]

        # -----------------------------------------------
        # vlcntt/{device_id}/status
        # vlcntt/{device_id}/audio/{action}
        # -----------------------------------------------

        if (
            len(parts) >= 3
            and parts[0] == "vlcntt"
        ):
            return parts[1]

        raise ValueError(
            f"Invalid MQTT topic: {topic}"
        )