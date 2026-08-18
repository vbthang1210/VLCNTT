from __future__ import annotations

import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock


_RECORDING_ID = re.compile(r"^rec_[A-Za-z0-9_-]+$")


class RecordingError(ValueError):
    pass


@dataclass
class RecordingSession:
    device_id: str
    recording_id: str
    pcm_path: Path
    sample_rate: int
    channels: int
    bits_per_sample: int
    max_bytes: int
    next_sequence: int = 0
    bytes_written: int = 0

    @property
    def frame_bytes(self) -> int:
        return self.channels * self.bits_per_sample // 8


class PcmRecordingService:
    """Collect ordered PCM MQTT chunks and persist a Backend-owned WAV file."""

    def __init__(self, repository, max_recording_seconds: int = 60):
        self.repository = repository
        self.max_recording_seconds = max(1, int(max_recording_seconds))
        self.temp_path = repository.storage_path / ".recordings"
        self.temp_path.mkdir(parents=True, exist_ok=True)
        self._sessions: dict[tuple[str, str], RecordingSession] = {}
        self._lock = Lock()

    def start(self, device_id: str, payload: dict) -> dict:
        if not isinstance(device_id, str) or not device_id:
            raise RecordingError("device_id is required")
        recording_id = payload.get("recording_id") or f"rec_{secrets.token_hex(4)}"
        if not isinstance(recording_id, str) or not _RECORDING_ID.fullmatch(recording_id):
            raise RecordingError("recording_id must use the rec_ prefix")

        sample_rate = payload.get("sample_rate", 16000)
        channels = payload.get("channels", 1)
        bits_per_sample = payload.get("bits_per_sample", 16)
        duration_seconds = payload.get("duration_seconds", self.max_recording_seconds)
        if (isinstance(sample_rate, bool) or not isinstance(sample_rate, int) or sample_rate != 16000):
            raise RecordingError("sample_rate must be 16000")
        if channels != 1 or bits_per_sample != 16:
            raise RecordingError("recording must be mono 16-bit PCM")
        if (isinstance(duration_seconds, bool) or not isinstance(duration_seconds, int)
                or not 1 <= duration_seconds <= self.max_recording_seconds):
            raise RecordingError("duration_seconds is outside the allowed range")
        if payload.get("device_id", device_id) != device_id:
            raise RecordingError("device_id does not match the MQTT topic")

        key = (device_id, recording_id)
        pcm_path = self.temp_path / f".{recording_id}.pcm"
        max_bytes = sample_rate * channels * (bits_per_sample // 8) * duration_seconds
        with self._lock:
            if key in self._sessions:
                raise RecordingError("recording is already active")
            pcm_path.unlink(missing_ok=True)
            pcm_path.touch()
            self._sessions[key] = RecordingSession(
                device_id=device_id,
                recording_id=recording_id,
                pcm_path=pcm_path,
                sample_rate=sample_rate,
                channels=channels,
                bits_per_sample=bits_per_sample,
                max_bytes=max_bytes,
            )
        return {
            "device_id": device_id,
            "recording_id": recording_id,
            "sample_rate": sample_rate,
            "channels": channels,
            "bits_per_sample": bits_per_sample,
        }

    def append_chunk(self, device_id: str, recording_id: str, sequence: int, payload: bytes) -> bool:
        if not isinstance(sequence, int) or sequence < 0:
            raise RecordingError("chunk sequence must be a non-negative integer")
        if not payload or len(payload) % 2:
            raise RecordingError("PCM chunk must contain non-empty 16-bit samples")
        key = (device_id, recording_id)
        with self._lock:
            session = self._sessions.get(key)
            if session is None:
                raise RecordingError("recording session is not active")
            if sequence < session.next_sequence:
                return False
            if sequence > session.next_sequence:
                raise RecordingError("PCM chunk sequence is out of order")
            if session.bytes_written + len(payload) > session.max_bytes:
                raise RecordingError("recording exceeds the duration limit")
            with session.pcm_path.open("ab") as output:
                output.write(payload)
            session.bytes_written += len(payload)
            session.next_sequence += 1
        return True

    def finish(self, device_id: str, payload: dict) -> dict:
        recording_id = payload.get("recording_id")
        if not isinstance(recording_id, str):
            raise RecordingError("recording_id is required")
        if payload.get("device_id", device_id) != device_id:
            raise RecordingError("device_id does not match the MQTT topic")
        key = (device_id, recording_id)
        with self._lock:
            session = self._sessions.get(key)
            if session is None:
                raise RecordingError("recording session is not active")
            total_chunks = payload.get("total_chunks")
            if total_chunks is not None and total_chunks != session.next_sequence:
                raise RecordingError("recording is missing PCM chunks")
            if session.bytes_written == 0 or session.bytes_written % session.frame_bytes:
                raise RecordingError("recording has no complete PCM frames")
            sample_count = payload.get("sample_count")
            expected_samples = session.bytes_written // session.frame_bytes
            if sample_count is not None and sample_count != expected_samples:
                raise RecordingError("sample_count does not match PCM payload")
            self._sessions.pop(key)

        frames = session.bytes_written // session.frame_bytes
        record = self.repository.save_pcm_recording(
            session.recording_id,
            session.pcm_path,
            session.sample_rate,
            session.channels,
            session.bits_per_sample,
            {
                "source": "INMP441",
                "device_id": session.device_id,
                "duration": frames / session.sample_rate,
                "sample_count": frames,
                "recorded_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        return record

    def abort(self, device_id: str, recording_id: str) -> None:
        with self._lock:
            session = self._sessions.pop((device_id, recording_id), None)
        if session is not None:
            session.pcm_path.unlink(missing_ok=True)


__all__ = ["PcmRecordingService", "RecordingError"]
