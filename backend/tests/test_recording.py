from __future__ import annotations

import io
import json
import struct
import sys
import wave
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app


@pytest.fixture()
def app(tmp_path):
    return create_app(
        {
            "TESTING": "true",
            "MQTT_ENABLED": "false",
            "AUDIO_STORAGE_PATH": str(tmp_path / "audio"),
            "METADATA_PATH": str(tmp_path / "metadata.json"),
        }
    )


def mqtt_message(topic: str, payload: bytes | dict):
    if isinstance(payload, dict):
        payload = json.dumps(payload).encode("utf-8")
    return SimpleNamespace(topic=topic, payload=payload)


def test_pcm_mqtt_session_creates_wav_and_metadata(app, tmp_path):
    mqtt_service = app.extensions["mqtt_service"]
    pcm = struct.pack("<hh", -1000, 2000)

    mqtt_service._on_message(
        None,
        None,
        mqtt_message(
            "esp32/esp32_01/audio/start",
            {
                "device_id": "esp32_01",
                "recording_id": "rec_test",
                "sample_rate": 16000,
                "channels": 1,
                "bits_per_sample": 16,
            },
        ),
    )
    mqtt_service._on_message(
        None,
        None,
        mqtt_message("esp32/esp32_01/audio/chunk/rec_test/0", pcm),
    )
    mqtt_service._on_message(
        None,
        None,
        mqtt_message(
            "esp32/esp32_01/audio/end",
            {
                "device_id": "esp32_01",
                "recording_id": "rec_test",
                "total_chunks": 1,
                "sample_count": 2,
            },
        ),
    )

    response = app.test_client().get("/api/v1/audio")
    assert response.status_code == 200
    record = response.json["data"][0]
    assert record["audio_id"] == "rec_test"
    assert record["filename"] == "rec_test.wav"
    assert record["source"] == "INMP441"
    assert record["sample_rate"] == 16000
    assert record["channels"] == 1
    assert record["bits_per_sample"] == 16
    assert record["status"] == "READY"

    streamed = app.test_client().get("/api/v1/audio/rec_test/stream")
    assert streamed.status_code == 200
    with wave.open(io.BytesIO(streamed.data), "rb") as wav:
        assert wav.getframerate() == 16000
        assert wav.getnchannels() == 1
        assert wav.getsampwidth() == 2
        assert wav.readframes(2) == pcm

    metadata = json.loads((tmp_path / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["rec_test"]["filename"] == "rec_test.wav"
    assert (tmp_path / "audio" / "rec_test.wav").is_file()


def test_record_routes_publish_start_and_stop_commands(app):
    calls = []

    class FakeMqttService:
        def publish_command(self, device_id, payload):
            calls.append((device_id, payload))
            return True

    app.extensions["mqtt_service"] = FakeMqttService()
    client = app.test_client()

    started = client.post(
        "/api/v1/devices/esp32_01/record/start",
        json={"duration_seconds": 3},
    )
    assert started.status_code == 202
    assert started.json["data"]["command"] == "START_RECORDING"
    recording_id = started.json["data"]["recording_id"]
    assert recording_id.startswith("rec_")
    assert calls[0][1]["duration_seconds"] == 3

    stopped = client.post(
        "/api/v1/devices/esp32_01/record/stop",
        json={"recording_id": recording_id},
    )
    assert stopped.status_code == 202
    assert calls[1][1] == {
        "request_id": stopped.json["data"]["request_id"],
        "command": "STOP_RECORDING",
        "recording_id": recording_id,
    }


def test_audio_download_returns_attachment(app):
    client = app.test_client()
    response = client.post(
        "/api/v1/audio/upload",
        data={"file": (io.BytesIO(b"RIFF"), "sample.wav")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 422

    valid = io.BytesIO()
    with wave.open(valid, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(b"\x00\x00")
    uploaded = client.post(
        "/api/v1/audio/upload",
        data={"file": (io.BytesIO(valid.getvalue()), "sample.wav")},
        content_type="multipart/form-data",
    )
    audio_id = uploaded.json["data"]["audio_id"]

    downloaded = client.get(f"/api/v1/audio/{audio_id}/download")
    assert downloaded.status_code == 200
    assert downloaded.mimetype == "audio/wav"
    assert "attachment" in downloaded.headers["Content-Disposition"]
