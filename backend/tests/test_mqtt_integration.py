from __future__ import annotations

import json
import os
import secrets
import socket
import sys
import time
from threading import Event
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    import paho.mqtt.client as mqtt
except ImportError:  # pragma: no cover
    mqtt = None


pytestmark = pytest.mark.skipif(mqtt is None, reason="paho-mqtt is unavailable")


def broker_available() -> bool:
    with socket.socket() as sock:
        sock.settimeout(1)
        try:
            sock.connect(("127.0.0.1", 1883))
            return True
        except OSError:
            return False


def test_local_broker_round_trip_qos1():
    if not broker_available():
        pytest.skip("local Mosquitto is unavailable")
    username = os.environ.get("MQTT_TEST_USERNAME")
    password = os.environ.get("MQTT_TEST_PASSWORD")
    if not username or password is None:
        pytest.skip("MQTT_TEST_USERNAME and MQTT_TEST_PASSWORD are required for an authenticated broker")
    received = []
    done = Event()
    client = mqtt.Client(client_id="backend-test-subscriber")
    client.username_pw_set(username, password)

    def on_message(_client, _userdata, message):
        received.append((message.topic, json.loads(message.payload.decode())))
        done.set()

    client.on_message = on_message
    client.connect("127.0.0.1", 1883, 5)
    client.subscribe("integration/test", qos=1)
    client.loop_start()
    publisher = mqtt.Client(client_id="backend-test-publisher")
    publisher.username_pw_set(username, password)
    publisher.connect("127.0.0.1", 1883, 5)
    info = publisher.publish("integration/test", json.dumps({"ok": True}), qos=1)
    info.wait_for_publish(timeout=3)
    assert info.rc == mqtt.MQTT_ERR_SUCCESS
    assert done.wait(3)
    assert received == [("integration/test", {"ok": True})]
    publisher.disconnect()
    client.loop_stop()
    client.disconnect()


def test_local_broker_assembles_pcm_recording(tmp_path):
    if not broker_available():
        pytest.skip("local Mosquitto is unavailable")
    backend_username = os.environ.get("MQTT_USERNAME")
    backend_password = os.environ.get("MQTT_PASSWORD")
    device_username = os.environ.get("MQTT_DEVICE_USERNAME")
    device_password = os.environ.get("MQTT_DEVICE_PASSWORD")
    if not all((backend_username, backend_password, device_username, device_password)):
        pytest.skip("MQTT backend/device credentials are required for an authenticated broker")

    from app import create_app

    suffix = secrets.token_hex(3)
    device_id = f"esp32_test_{suffix}"
    recording_id = f"rec_{suffix}"
    app = create_app(
        {
            "TESTING": "true",
            "MQTT_ENABLED": "true",
            "MQTT_HOST": "127.0.0.1",
            "MQTT_PORT": "1883",
            "MQTT_USERNAME": backend_username,
            "MQTT_PASSWORD": backend_password,
            "AUDIO_STORAGE_PATH": str(tmp_path / "audio"),
            "METADATA_PATH": str(tmp_path / "metadata.json"),
        }
    )
    service = app.extensions["mqtt_service"]
    publisher = mqtt.Client(client_id=f"recording-publisher-{suffix}")
    publisher.username_pw_set(device_username, device_password)
    try:
        service.start()
        deadline = time.time() + 3
        while not service.is_connected() and time.time() < deadline:
            time.sleep(0.05)
        if not service.is_connected():
            pytest.skip("local Mosquitto did not accept the Backend client")

        publisher.connect("127.0.0.1", 1883, 5)
        publisher.loop_start()
        start = {
            "device_id": device_id,
            "recording_id": recording_id,
            "sample_rate": 16000,
            "channels": 1,
            "bits_per_sample": 16,
        }
        publisher.publish(
            f"esp32/{device_id}/audio/start", json.dumps(start), qos=1
        ).wait_for_publish(timeout=3)
        publisher.publish(
            f"esp32/{device_id}/audio/chunk/{recording_id}/0", b"\x01\x00\x02\x00", qos=1
        ).wait_for_publish(timeout=3)
        publisher.publish(
            f"esp32/{device_id}/audio/end",
            json.dumps({"device_id": device_id, "recording_id": recording_id, "total_chunks": 1}),
            qos=1,
        ).wait_for_publish(timeout=3)

        deadline = time.time() + 3
        record = None
        while record is None and time.time() < deadline:
            record = app.extensions["audio_repository"].get(recording_id)
            time.sleep(0.05)
        assert record is not None
        assert record["filename"] == f"{recording_id}.wav"
        assert record["sample_rate"] == 16000
    finally:
        publisher.loop_stop()
        publisher.disconnect()
        service.stop()
