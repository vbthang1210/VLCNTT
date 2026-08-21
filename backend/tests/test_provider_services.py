from __future__ import annotations

import io
import json
import sys
import wave
from urllib.error import HTTPError
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
from app.services.tts_service import TTSNotConfigured, TTSProviderError, TTSService
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


def test_edge_tts_saves_generated_audio_without_api_credentials():
    calls = []

    class FakeRepository:
        def save_upload(self, upload):
            calls.append((upload.filename, upload.stream.read()))
            return {"audio_id": "tts_edge_1", "format": "mp3", "status": "READY"}

    service = TTSService(
        provider="edge",
        repository=FakeRepository(),
        default_voice="vi-VN-HoaiMyNeural",
        response_format="mp3",
        edge_synthesizer=lambda text, voice: b"edge-mp3-bytes",
    )

    record = service.synthesize("Xin chào")

    assert record["source"] == "tts"
    assert calls == [("tts_edge_vi-VN-HoaiMyNeural.mp3", b"edge-mp3-bytes")]


def test_elevenlabs_tts_uses_voice_path_api_key_and_output_format(tmp_path):
    transport = CaptureTransport(FakeResponse(wav_bytes()))
    service = TTSService(
        provider="elevenlabs",
        repository=AudioRepository(tmp_path / "audio", tmp_path / "metadata.json", 20 * 1024 * 1024),
        api_url="https://api.elevenlabs.io/v1/text-to-speech",
        api_key="eleven-test-key",
        model="eleven_multilingual_v2",
        default_voice="voice-123",
        response_format="wav",
        opener=transport,
    )

    record = service.synthesize("hello")

    assert record["format"] == "wav"
    assert record["source"] == "tts"
    http_request, timeout = transport.requests[0]
    assert http_request.full_url.endswith(
        "/v1/text-to-speech/voice-123?output_format=wav_44100"
    )
    assert http_request.get_header("Xi-api-key") == "eleven-test-key"
    assert request_json(http_request) == {
        "text": "hello",
        "model_id": "eleven_multilingual_v2",
    }
    assert timeout == 15


def test_tts_provider_error_includes_http_status(tmp_path):
    transport = CaptureTransport(FakeResponse(b'{"detail":"invalid api key"}', status=401))
    service = TTSService(
        provider="elevenlabs",
        repository=AudioRepository(tmp_path / "audio", tmp_path / "metadata.json", 20 * 1024 * 1024),
        api_url="https://api.elevenlabs.io/v1/text-to-speech",
        api_key="bad-key",
        model="eleven_multilingual_v2",
        default_voice="voice-123",
        response_format="mp3",
        opener=transport,
    )

    with pytest.raises(RuntimeError, match="TTS provider HTTP 401"):
        service.synthesize("hello")


def test_tts_http_error_includes_provider_response_body(tmp_path):
    def failing_opener(_request, timeout):
        raise HTTPError(
            "https://api.elevenlabs.io/v1/text-to-speech/voice-123",
            400,
            "Bad Request",
            {},
            io.BytesIO(b'{"detail":"voice not found"}'),
        )

    service = TTSService(
        provider="elevenlabs",
        repository=AudioRepository(tmp_path / "audio", tmp_path / "metadata.json", 20 * 1024 * 1024),
        api_url="https://api.elevenlabs.io/v1/text-to-speech",
        api_key="test-key",
        model="eleven_multilingual_v2",
        default_voice="voice-123",
        response_format="mp3",
        opener=failing_opener,
    )

    with pytest.raises(RuntimeError, match="voice not found"):
        service.synthesize("hello")


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


def test_tts_route_reports_provider_failure_as_bad_gateway(client):
    class FailingTTSService:
        def synthesize(self, text, voice=None):
            raise RuntimeError("provider HTTP 401")

    client.application.extensions["tts_service"] = FailingTTSService()

    response = client.post("/api/v1/audio/tts", json={"text": "hello"})

    assert response.status_code == 502
    assert response.json["error"]["code"] == "TTS_PROVIDER_FAILED"


def test_tts_route_keeps_local_audio_when_cloud_sync_fails(client):
    class FakeTTSService:
        def synthesize(self, text, voice=None):
            return {"audio_id": "tts_local_1", "filename": "tts_local_1.mp3", "format": "mp3"}

    class FailingCloudService:
        def save_metadata(self, record):
            raise RuntimeError("cloud unavailable")

    client.application.extensions["tts_service"] = FakeTTSService()
    client.application.extensions["cloud_service"] = FailingCloudService()

    response = client.post("/api/v1/audio/tts", json={"text": "hello"})

    assert response.status_code == 201
    assert response.json["data"]["cloud_synced"] is False


def test_non_elevenlabs_provider_404_is_not_labeled_as_voice_not_found(client):
    class FailingTTSService:
        def synthesize(self, text, voice=None):
            raise TTSProviderError(status=404, provider_code="not_found", message="not found")

    client.application.extensions["tts_service"] = FailingTTSService()

    response = client.post("/api/v1/audio/tts", json={"text": "hello"})

    assert response.status_code == 502
    assert response.json["error"]["code"] == "TTS_PROVIDER_FAILED"


def test_tts_plan_error_is_reported_as_actionable_payment_error(client):
    class PaidPlanTTSService:
        def synthesize(self, text, voice=None):
            raise TTSProviderError(
                status=402,
                provider_code="paid_plan_required",
                message="Free users cannot use library voices via the API",
            )

    client.application.extensions["tts_service"] = PaidPlanTTSService()
    response = client.post("/api/v1/audio/tts", json={"text": "hello"})

    assert response.status_code == 402
    assert response.json["error"]["code"] == "TTS_PLAN_REQUIRED"


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


def test_firestore_http_failure_reports_status_and_detail():
    transport = CaptureTransport(FakeResponse(b'{"error":{"status":"PERMISSION_DENIED"}}', status=403))
    service = CloudService(
        provider="firestore",
        project_id="project-test",
        access_token="token-test",
        opener=transport,
    )

    with pytest.raises(RuntimeError, match="Firestore metadata HTTP 403"):
        service.save_metadata({"audio_id": "audio_1"})


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


def test_firestore_lists_audio_metadata_documents():
    transport = CaptureTransport(
        FakeResponse(
            json.dumps(
                {
                    "documents": [
                        {
                            "name": "projects/project-test/databases/(default)/documents/audio_metadata/audio_1234",
                            "fields": {
                                "audio_id": {"stringValue": "audio_1234"},
                                "filename": {"stringValue": "audio_1234.wav"},
                                "duration": {"doubleValue": 1.25},
                                "sample_rate": {"integerValue": "16000"},
                                "status": {"stringValue": "READY"},
                            },
                        }
                    ]
                }
            ).encode()
        )
    )
    service = CloudService(
        provider="firestore",
        project_id="project-test",
        access_token="token-test",
        collection="audio_metadata",
        opener=transport,
    )

    records = service.list_metadata()

    assert records == [
        {
            "audio_id": "audio_1234",
            "filename": "audio_1234.wav",
            "duration": 1.25,
            "sample_rate": 16000,
            "status": "READY",
            "cloud_synced": True,
        }
    ]
    http_request, timeout = transport.requests[0]
    assert http_request.full_url.endswith(
        "/v1/projects/project-test/databases/(default)/documents/audio_metadata?pageSize=100"
    )
    assert http_request.get_header("Authorization") == "Bearer token-test"
    assert timeout == 10


def test_audio_api_merges_cloud_metadata_with_local_records(client):
    class FakeCloudService:
        def list_metadata(self):
            return [
                {
                    "audio_id": "cloud_only",
                    "filename": "cloud_only.wav",
                    "duration": 2.5,
                    "format": "wav",
                    "status": "READY",
                    "cloud_synced": True,
                }
            ]

    client.application.extensions["cloud_service"] = FakeCloudService()

    response = client.get("/api/v1/audio")

    assert response.status_code == 200
    assert response.json["data"] == [
        {
            "audio_id": "cloud_only",
            "filename": "cloud_only.wav",
            "duration": 2.5,
            "format": "wav",
            "status": "READY",
            "cloud_synced": True,
            "local_available": False,
        }
    ]


def test_telegram_notification_sends_message_to_chat():
    transport = CaptureTransport(FakeResponse(b'{"ok":true,"result":{"message_id":1}}'))
    service = NotificationService(
        provider="telegram",
        telegram_bot_token="bot-token",
        telegram_chat_id="12345",
        opener=transport,
    )

    assert service.notify(
        {"device_id": "esp32_01", "event": "RECORDING_COMPLETED"}
    ) is True

    http_request, timeout = transport.requests[0]
    assert http_request.full_url == "https://api.telegram.org/botbot-token/sendMessage"
    assert request_json(http_request) == {
        "chat_id": "12345",
        "text": "🔔 ESP32 event: RECORDING_COMPLETED\nesp32_01: RECORDING_COMPLETED",
        "disable_web_page_preview": True,
    }
    assert timeout == 10


def test_telegram_notification_requires_configuration():
    with pytest.raises(NotificationNotConfigured):
        NotificationService(provider="telegram").notify({"event": "DEVICE_OFFLINE"})


def test_telegram_notification_formats_online_status():
    transport = CaptureTransport(FakeResponse(b'{"ok":true,"result":{"message_id":1}}'))
    service = NotificationService(
        provider="telegram",
        telegram_bot_token="bot-token",
        telegram_chat_id="12345",
        opener=transport,
    )

    assert service.notify({"device_id": "esp32_01", "status": "ONLINE"}) is True

    assert request_json(transport.requests[0][0])["text"] == (
        "🔔 ESP32 online\nesp32_01 is online"
    )


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


def test_mqtt_online_status_dispatches_notification_on_transition():
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
        retain=True,
        payload=b'{"device_id":"esp32_01","status":"ONLINE"}',
    )

    service._on_message(None, None, message)

    assert calls == [{"device_id": "esp32_01", "status": "ONLINE"}]


def test_status_error_without_details_does_not_duplicate_error_notification():
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
        payload=b'{"device_id":"esp32_01","status":"ERROR"}',
    )

    service._on_message(None, None, message)

    assert calls == []


def test_retained_offline_status_does_not_notify_from_initial_offline_state():
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
        retain=True,
        payload=json.dumps(
            {
                "device_id": "esp32_01",
                "status": "OFFLINE",
                "reason": "UNEXPECTED_DISCONNECT",
            }
        ).encode(),
    )

    service._on_message(None, None, message)

    assert calls == []


def test_retained_offline_after_online_still_notifies():
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
    online = SimpleNamespace(
        topic="esp32/esp32_01/status",
        retain=True,
        payload=b'{"device_id":"esp32_01","status":"ONLINE"}',
    )
    offline = SimpleNamespace(
        topic="esp32/esp32_01/status",
        retain=True,
        payload=b'{"device_id":"esp32_01","status":"OFFLINE"}',
    )

    service._on_message(None, None, online)
    service._on_message(None, None, offline)

    assert calls == [
        {"device_id": "esp32_01", "status": "ONLINE"},
        {"device_id": "esp32_01", "status": "OFFLINE"},
    ]
