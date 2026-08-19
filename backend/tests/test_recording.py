from __future__ import annotations

import io
import json
import struct
import sys
import threading
import time
import wave
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app
from app.services.recording_service import PcmRecordingService, RecordingError


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


def test_resume_route_publishes_resume_command(app):
    calls = []

    class FakeMqttService:
        def publish_command(self, device_id, payload):
            calls.append((device_id, payload))
            return True

    app.extensions["mqtt_service"] = FakeMqttService()
    response = app.test_client().post(
        "/api/v1/devices/esp32_01/resume",
        json={"request_id": "req_resume"},
    )

    assert response.status_code == 202
    assert calls == [
        (
            "esp32_01",
            {"request_id": "req_resume", "command": "RESUME"},
        )
    ]


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


def test_incomplete_recording_is_removed_after_timeout(app):
    repository = app.extensions["audio_repository"]
    service = PcmRecordingService(repository, max_recording_seconds=60, session_timeout_seconds=0.1)
    service.start(
        "esp32_01",
        {
            "device_id": "esp32_01",
            "recording_id": "rec_timeout",
            "sample_rate": 16000,
            "channels": 1,
            "bits_per_sample": 16,
            "duration_seconds": 1,
        },
    )
    temp_path = repository.storage_path / ".recordings" / ".rec_timeout.pcm"
    assert temp_path.is_file()

    time.sleep(0.25)

    with pytest.raises(RecordingError, match="not active"):
        service.append_chunk("esp32_01", "rec_timeout", 0, b"\x00\x00")
    assert not temp_path.exists()


def test_inmp441_completion_dispatches_voice_processing(app):
    completed = threading.Event()
    records = []

    class FakeVoiceCommandService:
        def process(self, record):
            records.append(record)
            completed.set()

    mqtt_service = app.extensions["mqtt_service"]
    mqtt_service.set_voice_command_service(FakeVoiceCommandService())
    pcm = b"\x00\x00" * 16000
    try:
        mqtt_service._on_message(
            None,
            None,
            mqtt_message(
                "esp32/esp32_01/audio/start",
                {
                    "device_id": "esp32_01",
                    "recording_id": "rec_voice",
                    "sample_rate": 16000,
                    "channels": 1,
                    "bits_per_sample": 16,
                    "duration_seconds": 1,
                },
            ),
        )
        mqtt_service._on_message(
            None,
            None,
            mqtt_message("esp32/esp32_01/audio/chunk/rec_voice/0", pcm),
        )
        mqtt_service._on_message(
            None,
            None,
            mqtt_message(
                "esp32/esp32_01/audio/end",
                {
                    "device_id": "esp32_01",
                    "recording_id": "rec_voice",
                    "total_chunks": 1,
                    "sample_count": 16000,
                },
            ),
        )

        assert completed.wait(1)
        assert records[0]["audio_id"] == "rec_voice"
        assert records[0]["source"] == "INMP441"
    finally:
        mqtt_service.stop()


def test_voice_worker_handles_prediction_result_without_logger_error(app):
    class FakeVoiceCommandService:
        def process(self, record):
            return SimpleNamespace(reason="AI_UNAVAILABLE", published=False)

    mqtt_service = app.extensions["mqtt_service"]
    mqtt_service.set_voice_command_service(FakeVoiceCommandService())
    try:
        mqtt_service._process_voice_record(
            {"device_id": "esp32_01", "audio_id": "rec_voice"}
        )
    finally:
        mqtt_service.stop()


def test_voice_submission_after_stop_is_safe(app):
    mqtt_service = app.extensions["mqtt_service"]
    mqtt_service.stop()

    assert mqtt_service._submit_voice_record({"audio_id": "rec_voice"}) is False


def test_voice_executor_is_recreated_when_service_starts_again(app):
    mqtt_service = app.extensions["mqtt_service"]
    mqtt_service.stop()

    mqtt_service.start()

    try:
        assert mqtt_service._voice_executor is not None
    finally:
        mqtt_service.stop()
