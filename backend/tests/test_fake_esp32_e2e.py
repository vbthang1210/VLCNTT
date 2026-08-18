from __future__ import annotations

import io
import json
import socket
import subprocess
import sys
import time
import wave
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FAKE_ESP32 = PROJECT_ROOT / "tests" / "fake_esp32.py"

DEVICE_ID = "esp32_01"
MQTT_HOST = "127.0.0.1"
MQTT_PORT = 1883


def broker_available() -> bool:
    """Check whether Mosquitto is listening on localhost:1883."""
    with socket.socket() as sock:
        sock.settimeout(1)

        try:
            sock.connect((MQTT_HOST, MQTT_PORT))
            return True
        except OSError:
            return False


def wav_bytes() -> bytes:
    """Create a tiny valid WAV file for the upload test."""
    buffer = io.BytesIO()

    with wave.open(buffer, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(8000)

        # 0.1 second of silence
        output.writeframes(b"\x00\x00" * 800)

    return buffer.getvalue()


def wait_until(
    condition,
    timeout: float = 5.0,
    interval: float = 0.05,
) -> bool:
    """Wait until condition() becomes True."""
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        if condition():
            return True

        time.sleep(interval)

    return False


@pytest.fixture()
def backend():
    """
    Create a real Flask backend with MQTT enabled.

    The MQTT broker must already be running on localhost:1883.
    """
    if not broker_available():
        pytest.skip("Mosquitto is unavailable on 127.0.0.1:1883")

    from app import create_app

    app = create_app(
        {
            "TESTING": "true",
            "MQTT_ENABLED": "true",
            "MQTT_HOST": MQTT_HOST,
            "MQTT_PORT": MQTT_PORT,
            "AUDIO_STORAGE_PATH": str(
                PROJECT_ROOT / "test_artifacts" / "e2e_audio"
            ),
            "METADATA_PATH": str(
                PROJECT_ROOT / "test_artifacts" / "e2e_metadata.json"
            ),
        }
    )

    mqtt_service = app.extensions["mqtt_service"]

    # create_app() does not automatically start MQTT
    # because TESTING=true.
    mqtt_service.start()

    # Give Paho a short time to establish the connection.
    connected = wait_until(
        mqtt_service.is_connected,
        timeout=5,
    )

    if not connected:
        mqtt_service.stop()
        pytest.fail("Backend could not connect to Mosquitto")

    yield app

    mqtt_service.stop()


@pytest.fixture()
def fake_esp32():
    """
    Start the fake ESP32 as a separate Python process.
    """
    if not broker_available():
        pytest.skip("Mosquitto is unavailable on 127.0.0.1:1883")

    process = subprocess.Popen(
        [
            sys.executable,
            str(FAKE_ESP32),
        ],
        cwd=PROJECT_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    # Give the fake device time to connect and subscribe.
    time.sleep(1)

    yield process

    process.terminate()

    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def test_backend_fake_esp32_play_flow(
    backend,
    fake_esp32,
):
    """
    Full E2E test:

        Backend
          ↓
        MQTT PLAY
          ↓
        Fake ESP32
          ↓
        STATUS PLAYING
          ↓
        EVENT PLAY_COMPLETED
          ↓
        STATUS STOPPED
          ↓
        Backend DeviceState
    """
    client = backend.test_client()

    # ---------------------------------------------------------
    # 1. Wait for Fake ESP32 to appear ONLINE.
    # ---------------------------------------------------------

    state_store = backend.extensions["device_state"]

    online = wait_until(
        lambda: state_store.get(DEVICE_ID).status == "ONLINE",
        timeout=5,
    )

    assert online, (
        "Fake ESP32 never reported ONLINE. "
        "Check Mosquitto and fake_esp32.py."
    )

    # ---------------------------------------------------------
    # 2. Upload a real WAV file.
    # ---------------------------------------------------------

    upload = client.post(
        "/api/v1/audio/upload",
        data={
            "file": (
                io.BytesIO(wav_bytes()),
                "e2e_test.wav",
            )
        },
        content_type="multipart/form-data",
    )

    assert upload.status_code == 201, upload.json

    record = upload.json["data"]

    assert record["format"] == "wav"
    assert record["status"] == "READY"

    audio_id = record["audio_id"]

    # ---------------------------------------------------------
    # 3. Ask backend to PLAY the audio.
    # ---------------------------------------------------------

    response = client.post(
        f"/api/v1/devices/{DEVICE_ID}/play",
        json={
            "audio_id": audio_id,
            "request_id": "e2e_play_001",
        },
    )

    assert response.status_code == 202, response.json

    command_data = response.json["data"]

    assert command_data["request_id"] == "e2e_play_001"
    assert command_data["command"] == "PLAY"

    # ---------------------------------------------------------
    # 4. Fake ESP32 should report PLAYING.
    # ---------------------------------------------------------

    playing = wait_until(
        lambda: state_store.get(DEVICE_ID).status == "PLAYING",
        timeout=5,
    )

    assert playing, (
        "Backend never received PLAYING status from Fake ESP32"
    )

    state = state_store.get(DEVICE_ID)

    assert state.request_id == "e2e_play_001"

    # ---------------------------------------------------------
    # 5. Fake ESP32 should emit PLAY_COMPLETED.
    # ---------------------------------------------------------

    completed = wait_until(
        lambda: (
            state_store.get(DEVICE_ID).last_event is not None
            and state_store.get(DEVICE_ID).last_event.get("event")
            == "PLAY_COMPLETED"
        ),
        timeout=5,
    )

    assert completed, (
        "Backend never received PLAY_COMPLETED event"
    )

    event = state_store.get(DEVICE_ID).last_event

    assert event["device_id"] == DEVICE_ID
    assert event["event"] == "PLAY_COMPLETED"
    assert event["request_id"] == "e2e_play_001"

    # ---------------------------------------------------------
    # 6. Fake ESP32 should finally report STOPPED.
    # ---------------------------------------------------------

    stopped = wait_until(
        lambda: state_store.get(DEVICE_ID).status == "STOPPED",
        timeout=5,
    )

    assert stopped, (
        "Backend never received final STOPPED status"
    )

    state = state_store.get(DEVICE_ID)

    assert state.status == "STOPPED"
    assert state.request_id == "e2e_play_001"


def test_backend_fake_esp32_stop_flow(
    backend,
    fake_esp32,
):
    """
    Test:

        Backend → STOP → Fake ESP32 → STOPPED
    """
    client = backend.test_client()

    state_store = backend.extensions["device_state"]

    # Wait until fake device is online.
    assert wait_until(
        lambda: state_store.get(DEVICE_ID).status == "ONLINE",
        timeout=5,
    )

    response = client.post(
        f"/api/v1/devices/{DEVICE_ID}/stop",
        json={
            "request_id": "e2e_stop_001",
        },
    )

    assert response.status_code == 202, response.json

    assert response.json["data"]["command"] == "STOP"

    stopped = wait_until(
        lambda: (
            state_store.get(DEVICE_ID).status == "STOPPED"
            and state_store.get(DEVICE_ID).request_id
            == "e2e_stop_001"
        ),
        timeout=5,
    )

    assert stopped


def test_backend_fake_esp32_pause_flow(
    backend,
    fake_esp32,
):
    """
    Test:

        Backend → PAUSE → Fake ESP32 → PAUSED
    """
    client = backend.test_client()

    state_store = backend.extensions["device_state"]

    assert wait_until(
        lambda: state_store.get(DEVICE_ID).status == "ONLINE",
        timeout=5,
    )

    response = client.post(
        f"/api/v1/devices/{DEVICE_ID}/pause",
        json={
            "request_id": "e2e_pause_001",
        },
    )

    assert response.status_code == 202, response.json

    paused = wait_until(
        lambda: (
            state_store.get(DEVICE_ID).status == "PAUSED"
            and state_store.get(DEVICE_ID).request_id
            == "e2e_pause_001"
        ),
        timeout=5,
    )

    assert paused


def test_backend_fake_esp32_volume_flow(
    backend,
    fake_esp32,
):
    """
    Test:

        Backend → SET_VOLUME → Fake ESP32
                         ↓
                  VOLUME_CHANGED
                         ↓
                      Backend
    """
    client = backend.test_client()

    state_store = backend.extensions["device_state"]

    assert wait_until(
        lambda: state_store.get(DEVICE_ID).status == "ONLINE",
        timeout=5,
    )

    response = client.post(
        f"/api/v1/devices/{DEVICE_ID}/volume",
        json={
            "volume": 75,
            "request_id": "e2e_volume_001",
        },
    )

    assert response.status_code == 202, response.json

    changed = wait_until(
        lambda: (
            state_store.get(DEVICE_ID).last_event is not None
            and state_store.get(DEVICE_ID).last_event.get("event")
            == "VOLUME_CHANGED"
        ),
        timeout=5,
    )

    assert changed

    event = state_store.get(DEVICE_ID).last_event

    assert event["device_id"] == DEVICE_ID
    assert event["event"] == "VOLUME_CHANGED"
    assert event["request_id"] == "e2e_volume_001"