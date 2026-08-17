from __future__ import annotations

import io
import json
import sys
import wave
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.mqtt_service import DeviceStateStore, MqttService
from app.services.cloud_service import CloudNotConfigured, CloudService
from app.services.notification_service import (
    NotificationNotConfigured,
    NotificationService,
)
from app.services.tts_service import TTSNotConfigured, TTSService
from app.storage import AudioRepository


@pytest.fixture()
def client(tmp_path):
    from app import create_app

    app = create_app(
        {
            "TESTING": "true",
            "MQTT_ENABLED": "false",
            "AUDIO_STORAGE_PATH": str(tmp_path / "audio"),
            "METADATA_PATH": str(tmp_path / "metadata.json"),
        }
    )
    return app.test_client()


class FakeResponse:
    def __init__(self, body: bytes, status: int = 200):
        self.body = body
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self, limit=-1):
        return self.body if limit < 0 else self.body[:limit]


class CaptureTransport:
    def __init__(self, response: FakeResponse):
        self.response = response
        self.requests = []

    def __call__(self, request, timeout):
        self.requests.append((request, timeout))
        return self.response


def wav_bytes() -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(8000)
        output.writeframes(b"\x00\x00" * 80)
    return buffer.getvalue()


def request_json(request):
    return json.loads(request.data.decode("utf-8"))


def test_openai_compatible_tts_saves_provider_audio_in_backend_storage(tmp_path):
    repository = AudioRepository(tmp_path / "audio", tmp_path / "metadata.json", 20 * 1024 * 1024)
    transport = CaptureTransport(FakeResponse(wav_bytes()))
    service = TTSService(
        provider="openai_compatible",
        repository=repository,
        api_url="https://tts.example.test/v1/audio/speech",
        api_key="test-key",
        model="test-tts",
        default_voice="test-voice",
        response_format="wav",
        opener=transport,
    )

    record = service.synthesize("hello")

    assert record["format"] == "wav"
    assert record["original_filename"].startswith("tts_")
    assert repository.path_for(record["audio_id"]).read_bytes() == wav_bytes()
    request, timeout = transport.requests[0]
    assert request.full_url == "https://tts.example.test/v1/audio/speech"
    assert request.get_header("Authorization") == "Bearer test-key"
    assert request_json(request) == {
        "model": "test-tts",
        "input": "hello",
        "voice": "test-voice",
        "response_format": "wav",
    }
    assert timeout == 15


def test_tts_provider_requires_endpoint_and_model():
    with pytest.raises(TTSNotConfigured):
        TTSService(provider="openai_compatible").synthesize("hello")


def test_tts_route_persists_generated_audio_metadata_through_cloud(client):
    calls = []

    class FakeTTSService:
        def synthesize(self, text, voice=None):
            return {
                "audio_id": "audio_tts_1",
                "filename": "tts_1.mp3",
                "format": "mp3",
                "status": "READY",
            }

    class FakeCloudService:
        def save_metadata(self, record):
            calls.append(record)
            return {**record, "cloud_synced": True}

    client.application.extensions["tts_service"] = FakeTTSService()
    client.application.extensions["cloud_service"] = FakeCloudService()

    response = client.post("/api/v1/audio/tts", json={"text": "hello"})

    assert response.status_code == 201
    assert response.json["data"]["cloud_synced"] is True
    assert calls == [{
        "audio_id": "audio_tts_1",
        "filename": "tts_1.mp3",
        "format": "mp3",
        "status": "READY",
    }]


def test_firestore_metadata_persists_only_light_audio_metadata():
    transport = CaptureTransport(FakeResponse(b'{"name":"stored"}'))
    service = CloudService(
        provider="firestore",
        project_id="project-test",
        access_token="token-test",
        collection="audio_metadata",
        opener=transport,
    )
    record = {
        "audio_id": "audio_1234",
        "filename": "audio_1234.wav",
        "original_filename": "voice.wav",
        "duration": 1.25,
        "format": "wav",
        "sample_rate": 8000,
        "size": 1644,
        "status": "READY",
        "private_path": "must-not-leave-backend",
    }

    result = service.save_metadata(record)

    assert result["cloud_synced"] is True
    request, timeout = transport.requests[0]
    assert request.full_url.endswith(
        "/v1/projects/project-test/databases/(default)/documents/audio_metadata/audio_1234"
    )
    assert request.get_header("Authorization") == "Bearer token-test"
    payload = request_json(request)
    assert set(payload["fields"]) == {
        "audio_id",
        "filename",
        "original_filename",
        "duration",
        "format",
        "sample_rate",
        "size",
        "status",
    }
    assert "private_path" not in payload["fields"]
    assert timeout == 10


def test_firestore_requires_credentials():
    with pytest.raises(CloudNotConfigured):
        CloudService(provider="firestore").save_metadata({"audio_id": "audio_1"})


def test_firestore_persists_device_status_in_separate_document():
    transport = CaptureTransport(FakeResponse(b'{"name":"stored"}'))
    service = CloudService(
        provider="firestore",
        project_id="project-test",
        access_token="token-test",
        collection="audio_metadata",
        opener=transport,
    )

    result = service.save_status(
        {"device_id": "esp32_01", "status": "ONLINE", "reason": "CONNECTED"}
    )

    assert result["cloud_synced"] is True
    http_request, timeout = transport.requests[0]
    assert http_request.full_url.endswith(
        "/v1/projects/project-test/databases/(default)/documents/device_status/esp32_01"
    )
    payload = request_json(http_request)
    assert payload["fields"] == {
        "device_id": {"stringValue": "esp32_01"},
        "status": {"stringValue": "ONLINE"},
        "reason": {"stringValue": "CONNECTED"},
    }
    assert timeout == 10


def test_fcm_notification_sends_event_to_device():
    transport = CaptureTransport(FakeResponse(b'{"name":"message-id"}'))
    service = NotificationService(
        provider="fcm",
        project_id="project-test",
        access_token="token-test",
        device_token="device-token",
        opener=transport,
    )

    assert service.notify(
        {
            "device_id": "esp32_01",
            "event": "PLAY_COMPLETED",
            "request_id": "req_1",
            "audio_id": "audio_1",
        }
    ) is True

    request, timeout = transport.requests[0]
    assert request.full_url.endswith("/v1/projects/project-test/messages:send")
    assert request.get_header("Authorization") == "Bearer token-test"
    payload = request_json(request)
    assert payload["message"]["token"] == "device-token"
    assert payload["message"]["data"]["event"] == "PLAY_COMPLETED"
    assert payload["message"]["data"]["request_id"] == "req_1"
    assert timeout == 10


def test_fcm_notification_requires_configuration():
    with pytest.raises(NotificationNotConfigured):
        NotificationService(provider="fcm").notify({"event": "DEVICE_OFFLINE"})


def test_upload_persists_audio_metadata_through_cloud_service(client):
    calls = []

    class FakeCloudService:
        def save_metadata(self, record):
            calls.append(record)
            return {**record, "cloud_synced": True}

    client.application.extensions["cloud_service"] = FakeCloudService()
    response = client.post(
        "/api/v1/audio/upload",
        data={"file": (io.BytesIO(wav_bytes()), "cloud.wav")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 201
    assert response.json["data"]["cloud_synced"] is True
    assert calls[0]["audio_id"] == response.json["data"]["audio_id"]


def test_mqtt_event_dispatches_push_notification():
    calls = []

    class FakeNotificationService:
        def notify(self, event):
            calls.append(event)
            return True

    settings = SimpleNamespace(
        mqtt_enabled=True,
        mqtt_host="127.0.0.1",
        mqtt_port=1883,
        mqtt_username=None,
        mqtt_password=None,
    )
    service = MqttService(
        settings,
        DeviceStateStore(),
        notification_service=FakeNotificationService(),
    )
    message = SimpleNamespace(
        topic="esp32/esp32_01/event",
        payload=json.dumps(
            {
                "device_id": "esp32_01",
                "event": "PLAY_COMPLETED",
                "request_id": "req_1",
            }
        ).encode(),
    )

    service._on_message(None, None, message)

    assert calls == [
        {
            "device_id": "esp32_01",
            "event": "PLAY_COMPLETED",
            "request_id": "req_1",
        }
    ]


def test_mqtt_status_persists_to_cloud_service():
    calls = []

    class FakeCloudService:
        def save_status(self, status):
            calls.append(status)
            return {**status, "cloud_synced": True}

    settings = SimpleNamespace(
        mqtt_enabled=True,
        mqtt_host="127.0.0.1",
        mqtt_port=1883,
        mqtt_username=None,
        mqtt_password=None,
    )
    service = MqttService(
        settings,
        DeviceStateStore(),
        cloud_service=FakeCloudService(),
    )
    message = SimpleNamespace(
        topic="esp32/esp32_01/status",
        payload=json.dumps(
            {"device_id": "esp32_01", "status": "ONLINE"}
        ).encode(),
    )

    service._on_message(None, None, message)

    assert calls == [{"device_id": "esp32_01", "status": "ONLINE"}]


def test_mqtt_offline_status_dispatches_push_notification():
    calls = []

    class FakeNotificationService:
        def notify(self, event):
            calls.append(event)
            return True

    settings = SimpleNamespace(
        mqtt_enabled=True,
        mqtt_host="127.0.0.1",
        mqtt_port=1883,
        mqtt_username=None,
        mqtt_password=None,
    )
    service = MqttService(
        settings,
        DeviceStateStore(),
        notification_service=FakeNotificationService(),
    )
    message = SimpleNamespace(
        topic="esp32/esp32_01/status",
        payload=json.dumps(
            {
                "device_id": "esp32_01",
                "status": "OFFLINE",
                "reason": "UNEXPECTED_DISCONNECT",
            }
        ).encode(),
    )

    service._on_message(None, None, message)

    assert calls[0]["status"] == "OFFLINE"
