from __future__ import annotations

import json
import threading
import time

import paho.mqtt.client as mqtt


# ============================================================
# CONFIG
# ============================================================

DEVICE_ID = "esp32_01"

MQTT_HOST = "127.0.0.1"
MQTT_PORT = 1883

COMMAND_TOPIC = f"esp32/{DEVICE_ID}/command"
STATUS_TOPIC = f"esp32/{DEVICE_ID}/status"
EVENT_TOPIC = f"esp32/{DEVICE_ID}/event"
ERROR_TOPIC = f"esp32/{DEVICE_ID}/error"


# ============================================================
# MQTT CLIENT
# ============================================================

client = mqtt.Client(
    callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
    client_id=f"fake-{DEVICE_ID}",
)


# ============================================================
# PUBLISH STATUS
# ============================================================

def publish_status(
    status: str,
    request_id: str | None = None,
    reason: str | None = None,
):
    payload = {
        "device_id": DEVICE_ID,
        "status": status,
    }

    if request_id is not None:
        payload["request_id"] = request_id

    if reason is not None:
        payload["reason"] = reason

    info = client.publish(
        STATUS_TOPIC,
        json.dumps(payload),
        qos=1,
    )

    print(
        f"[ESP32] STATUS -> {status}"
    )

    return info


# ============================================================
# PUBLISH EVENT
# ============================================================

def publish_event(
    event: str,
    request_id: str | None = None,
    extra: dict | None = None,
):
    payload = {
        "device_id": DEVICE_ID,
        "event": event,
    }

    if request_id is not None:
        payload["request_id"] = request_id

    if extra:
        payload.update(extra)

    info = client.publish(
        EVENT_TOPIC,
        json.dumps(payload),
        qos=1,
    )

    print(
        f"[ESP32] EVENT -> {event}"
    )

    return info


# ============================================================
# PUBLISH ERROR
# ============================================================

def publish_error(
    error_code: str,
    message: str,
    request_id: str | None = None,
):
    payload = {
        "device_id": DEVICE_ID,
        "error_code": error_code,
        "message": message,
    }

    if request_id is not None:
        payload["request_id"] = request_id

    info = client.publish(
        ERROR_TOPIC,
        json.dumps(payload),
        qos=1,
    )

    print(
        f"[ESP32] ERROR -> {error_code}"
    )

    return info


# ============================================================
# SIMULATE PLAY
# ============================================================

def simulate_play(
    audio_id: str,
    request_id: str | None,
):
    """
    Simulate ESP32 playing an audio file.

    This runs in a separate thread so that the MQTT
    callback is never blocked.
    """

    print(
        f"[ESP32] Playing audio: {audio_id}"
    )

    # --------------------------------------------------------
    # PLAYING
    # --------------------------------------------------------

    publish_status(
        "PLAYING",
        request_id,
    )

    # --------------------------------------------------------
    # Simulate audio playback
    # --------------------------------------------------------

    time.sleep(1)

    # --------------------------------------------------------
    # PLAY COMPLETED
    # --------------------------------------------------------

    publish_event(
        "PLAY_COMPLETED",
        request_id,
    )

    # --------------------------------------------------------
    # STOPPED
    # --------------------------------------------------------

    publish_status(
        "STOPPED",
        request_id,
    )


# ============================================================
# MQTT CONNECT
# ============================================================

def on_connect(
    client,
    userdata,
    flags,
    reason_code,
    properties=None,
):
    print(
        f"[ESP32] Connected to MQTT: {reason_code}"
    )

    result, _mid = client.subscribe(
        COMMAND_TOPIC,
        qos=1,
    )

    if result == mqtt.MQTT_ERR_SUCCESS:
        print(
            f"[ESP32] Subscribed: {COMMAND_TOPIC}"
        )
    else:
        print(
            f"[ESP32] Failed to subscribe: {COMMAND_TOPIC}"
        )

    # Tell Backend that the ESP32 is online.
    publish_status("ONLINE")


# ============================================================
# MQTT MESSAGE
# ============================================================

def on_message(
    client,
    userdata,
    message,
):
    print()
    print(
        f"[ESP32] COMMAND <- {message.topic}"
    )

    try:
        payload = json.loads(
            message.payload.decode("utf-8")
        )
    except Exception as exc:
        print(
            f"[ESP32] Invalid JSON: {exc}"
        )
        return

    print(
        f"[ESP32] Payload: {payload}"
    )

    command = payload.get("command")
    request_id = payload.get("request_id")

    # ========================================================
    # PLAY
    # ========================================================

    if command == "PLAY":
        audio_id = payload.get("audio_id")

        thread = threading.Thread(
            target=simulate_play,
            args=(audio_id, request_id),
            daemon=True,
        )

        thread.start()

    # ========================================================
    # STOP
    # ========================================================

    elif command == "STOP":

        publish_status(
            "STOPPED",
            request_id,
        )

    # ========================================================
    # PAUSE
    # ========================================================

    elif command == "PAUSE":

        publish_status(
            "PAUSED",
            request_id,
        )

    # ========================================================
    # SET VOLUME
    # ========================================================

    elif command == "SET_VOLUME":

        volume = payload.get("volume")

        print(
            f"[ESP32] Volume = {volume}"
        )

        publish_event(
            "VOLUME_CHANGED",
            request_id,
            {
                "volume": volume,
            },
        )

    # ========================================================
    # UNKNOWN COMMAND
    # ========================================================

    else:

        publish_error(
            "UNKNOWN_COMMAND",
            f"Unknown command: {command}",
            request_id,
        )


# ============================================================
# MQTT DISCONNECT
# ============================================================

def on_disconnect(
    client,
    userdata,
    disconnect_flags,
    reason_code,
    properties=None,
):
    print(
        f"[ESP32] Disconnected: {reason_code}"
    )


# ============================================================
# REGISTER CALLBACKS
# ============================================================

client.on_connect = on_connect
client.on_message = on_message
client.on_disconnect = on_disconnect


# ============================================================
# START
# ============================================================

print(
    "[ESP32] Starting fake ESP32..."
)

client.connect(
    MQTT_HOST,
    MQTT_PORT,
    60,
)

client.loop_forever()