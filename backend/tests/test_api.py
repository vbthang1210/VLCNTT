from __future__ import annotations

import io
import sys
import wave
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app


@pytest.fixture()
def client(tmp_path):
    app = create_app(
        {
            "TESTING": "true",
            "MQTT_ENABLED": "false",
            "AUDIO_STORAGE_PATH": str(tmp_path / "audio"),
            "METADATA_PATH": str(tmp_path / "metadata.json"),
        }
    )
    return app.test_client()


def wav_bytes() -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(8000)
        output.writeframes(b"\x00\x00" * 800)
    return buffer.getvalue()


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json["success"] is True


def test_upload_list_and_stream_audio(client):
    response = client.post(
        "/api/v1/audio/upload",
        data={"file": (io.BytesIO(wav_bytes()), "tone.wav")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 201
    record = response.json["data"]
    assert record["format"] == "wav"
    assert record["status"] == "READY"

    listed = client.get("/api/v1/audio")
    assert listed.status_code == 200
    assert listed.json["data"][0]["audio_id"] == record["audio_id"]

    streamed = client.get(f"/api/v1/audio/{record['audio_id']}/stream")
    assert streamed.status_code == 200
    assert streamed.mimetype == "audio/wav"
    assert streamed.data == wav_bytes()


def test_unknown_audio_is_404(client):
    response = client.get("/api/v1/audio/audio_missing/stream")
    assert response.status_code == 404
    assert response.json["error"]["code"] == "AUDIO_NOT_FOUND"


def test_play_requires_existing_audio(client):
    response = client.post(
        "/api/v1/devices/esp32_01/play",
        json={"audio_id": "audio_missing"},
    )
    assert response.status_code == 404
    assert response.json["error"]["code"] == "AUDIO_NOT_FOUND"


def test_volume_range(client):
    response = client.post(
        "/api/v1/devices/esp32_01/volume",
        json={"volume": 101},
    )
    assert response.status_code == 400
    assert response.json["error"]["code"] == "VOLUME_INVALID"


def test_tts_is_explicitly_unconfigured(client):
    response = client.post("/api/v1/audio/tts", json={"text": "hello"})
    assert response.status_code == 501
    assert response.json["error"]["code"] == "TTS_NOT_CONFIGURED"


def test_device_status_is_not_claimed_playing_after_command_without_device(client):
    response = client.get("/api/v1/devices/esp32_01/status")
    assert response.status_code == 200
    assert response.json["data"]["status"] == "OFFLINE"
