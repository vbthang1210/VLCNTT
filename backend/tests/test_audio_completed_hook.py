import json

from app.services.audio_stream_service import AudioStreamService
from app.storage import AudioRepository


def repository(tmp_path):
    return AudioRepository(
        storage_path=tmp_path / "audio",
        metadata_path=tmp_path / "metadata.json",
        max_audio_size=1024 * 1024,
    )


def start_payload(device_id="esp32_01", session_id="voice_001") -> bytes:
    return json.dumps(
        {
            "device_id": device_id,
            "session_id": session_id,
            "sample_rate": 16000,
            "channels": 1,
            "sample_width": 2,
            "encoding": "pcm_s16le",
        }
    ).encode()


def end_payload(device_id="esp32_01", session_id="voice_001") -> bytes:
    return json.dumps(
        {
            "device_id": device_id,
            "session_id": session_id,
        }
    ).encode()


def test_completed_audio_invokes_handler_after_wav_is_saved(tmp_path):
    repo = repository(tmp_path)
    completed = []
    service = AudioStreamService(
        repo,
        on_completed=lambda record: completed.append(record),
    )

    service.start(start_payload())
    service.receive_data(
        "esp32_01",
        b"\x00\x00" * 1600,
    )

    record = service.end(end_payload())

    assert completed == [record]
    assert record["device_id"] == "esp32_01"
    assert record["session_id"] == "voice_001"
    assert repo.path_for(record["audio_id"]).is_file()
    assert service.has_active_session("esp32_01") is False


def test_completed_handler_failure_does_not_lose_saved_audio(tmp_path):
    repo = repository(tmp_path)

    def failing_handler(_record):
        raise RuntimeError("AI failed")

    service = AudioStreamService(
        repo,
        on_completed=failing_handler,
    )

    service.start(start_payload(session_id="voice_002"))
    service.receive_data(
        "esp32_01",
        b"\x00\x00" * 1600,
    )

    record = service.end(
        end_payload(session_id="voice_002")
    )

    assert repo.path_for(record["audio_id"]).is_file()
    assert service.has_active_session("esp32_01") is False
