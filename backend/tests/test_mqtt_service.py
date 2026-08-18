from __future__ import annotations

import json
from types import SimpleNamespace

from app.mqtt_service import DeviceStateStore, MqttService


def service_for_test():
    settings = SimpleNamespace(
        mqtt_enabled=True,
        mqtt_host="127.0.0.1",
        mqtt_port=1883,
        mqtt_username=None,
        mqtt_password=None,
    )
    store = DeviceStateStore()
    return MqttService(settings, store), store


def message(topic: str, payload: dict):
    return SimpleNamespace(topic=topic, payload=json.dumps(payload).encode())


def test_error_topic_becomes_error_state_with_error_details():
    service, store = service_for_test()
    service._on_message(
        None,
        None,
        message(
            "esp32/esp32_01/error",
            {
                "device_id": "esp32_01",
                "request_id": "req_1",
                "error_code": "AUDIO_DOWNLOAD_FAILED",
                "message": "Unable to open audio stream",
            },
        ),
    )

    state = store.get("esp32_01")
    assert state.status == "ERROR"
    assert state.request_id == "req_1"
    assert state.error == {
        "code": "AUDIO_DOWNLOAD_FAILED",
        "message": "Unable to open audio stream",
    }


def test_stale_status_does_not_replace_current_request():
    service, store = service_for_test()
    store.set_current_request("esp32_01", "req_2")
    service._on_message(
        None,
        None,
        message(
            "esp32/esp32_01/status",
            {
                "device_id": "esp32_01",
                "request_id": "req_2",
                "status": "PLAYING",
            },
        ),
    )
    service._on_message(
        None,
        None,
        message(
            "esp32/esp32_01/status",
            {
                "device_id": "esp32_01",
                "request_id": "req_1",
                "status": "STOPPED",
            },
        ),
    )

    state = store.get("esp32_01")
    assert state.status == "PLAYING"
    assert state.request_id == "req_2"


def test_event_topic_is_stored_without_changing_device_status():
    service, store = service_for_test()
    service._on_message(
        None,
        None,
        message(
            "esp32/esp32_01/event",
            {
                "device_id": "esp32_01",
                "request_id": "req_3",
                "event": "PLAY_COMPLETED",
            },
        ),
    )

    state = store.get("esp32_01")
    assert state.status == "OFFLINE"
    assert state.last_event["event"] == "PLAY_COMPLETED"


def test_light_changed_event_updates_light_state_without_overwriting_audio_status():
    service, store = service_for_test()
    store.update_status("esp32_01", "PLAYING", "play_001")

    service._on_message(
        None,
        None,
        message(
            "esp32/esp32_01/event",
            {
                "device_id": "esp32_01",
                "request_id": "ai_voice_001",
                "event": "LIGHT_CHANGED",
                "light_state": "ON",
            },
        ),
    )

    state = store.get("esp32_01")
    assert state.status == "PLAYING"
    assert state.request_id == "play_001"
    assert state.light_state == "ON"
    assert state.last_event == {
        "device_id": "esp32_01",
        "request_id": "ai_voice_001",
        "event": "LIGHT_CHANGED",
        "light_state": "ON",
    }
