from __future__ import annotations

import json
import socket
import time
from threading import Event

import pytest

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
    received = []
    done = Event()
    client = mqtt.Client(client_id="backend-test-subscriber")

    def on_message(_client, _userdata, message):
        received.append((message.topic, json.loads(message.payload.decode())))
        done.set()

    client.on_message = on_message
    client.connect("127.0.0.1", 1883, 5)
    client.subscribe("integration/test", qos=1)
    client.loop_start()
    publisher = mqtt.Client(client_id="backend-test-publisher")
    publisher.connect("127.0.0.1", 1883, 5)
    info = publisher.publish("integration/test", json.dumps({"ok": True}), qos=1)
    info.wait_for_publish(timeout=3)
    assert info.rc == mqtt.MQTT_ERR_SUCCESS
    assert done.wait(3)
    assert received == [("integration/test", {"ok": True})]
    publisher.disconnect()
    client.loop_stop()
    client.disconnect()
