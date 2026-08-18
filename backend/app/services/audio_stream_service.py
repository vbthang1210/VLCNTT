from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Callable

from ..storage import AudioRepository
from .audio_service import get_pcm_info, pcm_to_wav

logger = logging.getLogger(__name__)


@dataclass
class AudioSession:
    device_id: str
    session_id: str
    sample_rate: int
    channels: int
    sample_width: int
    encoding: str
    buffer: bytearray = field(default_factory=bytearray)
    packet_count: int = 0
    started_at: float = field(default_factory=time.time)
    last_packet_at: float = field(default_factory=time.time)

    def append(self, payload: bytes) -> None:
        if not payload:
            return
        self.buffer.extend(payload)
        self.packet_count += 1
        self.last_packet_at = time.time()

    @property
    def size(self) -> int:
        return len(self.buffer)

    def expired(self, timeout: int) -> bool:
        return time.time() - self.last_packet_at > timeout


class AudioStreamService:
    def __init__(
        self,
        repository: AudioRepository,
        session_timeout: int = 5,
        on_completed: Callable[[dict], object] | None = None,
    ):
        self.repository = repository
        self.session_timeout = session_timeout
        self.on_completed = on_completed
        self.sessions: dict[str, AudioSession] = {}

    def set_completed_handler(
        self,
        handler: Callable[[dict], object] | None,
    ) -> None:
        self.on_completed = handler

    def start(self, payload: bytes) -> AudioSession:
        try:
            data = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("Invalid audio START payload") from exc

        required_fields = (
            "device_id",
            "session_id",
            "sample_rate",
            "channels",
            "sample_width",
            "encoding",
        )
        for field_name in required_fields:
            if field_name not in data:
                raise ValueError(f"Missing START field: {field_name}")

        device_id = str(data["device_id"])
        session_id = str(data["session_id"])

        if not device_id:
            raise ValueError("device_id is empty")
        if not session_id:
            raise ValueError("session_id is empty")

        existing = self.sessions.get(device_id)
        if existing is not None and existing.expired(self.session_timeout):
            logger.warning(
                "[AUDIO] Dropping expired session | device=%s | session=%s",
                device_id,
                existing.session_id,
            )
            del self.sessions[device_id]

        if device_id in self.sessions:
            raise ValueError(
                f"Device already has an active audio session: {device_id}"
            )

        sample_rate = int(data["sample_rate"])
        channels = int(data["channels"])
        sample_width = int(data["sample_width"])
        encoding = str(data["encoding"])

        if sample_rate <= 0:
            raise ValueError("Invalid sample_rate")
        if channels <= 0:
            raise ValueError("Invalid channels")
        if sample_width <= 0:
            raise ValueError("Invalid sample_width")
        if encoding != "pcm_s16le":
            raise ValueError(f"Unsupported audio encoding: {encoding}")

        session = AudioSession(
            device_id=device_id,
            session_id=session_id,
            sample_rate=sample_rate,
            channels=channels,
            sample_width=sample_width,
            encoding=encoding,
        )
        self.sessions[device_id] = session
        return session

    def receive_data(
        self,
        device_id: str,
        payload: bytes,
    ) -> None:
        session = self.sessions.get(device_id)
        if session is None:
            raise ValueError(
                f"Received audio DATA without an active session: {device_id}"
            )
        if not payload:
            return

        new_size = session.size + len(payload)
        if new_size > self.repository.max_audio_size:
            raise ValueError(
                "Audio session exceeds maximum allowed audio size"
            )

        session.append(payload)

    def end(self, payload: bytes) -> dict:
        try:
            data = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("Invalid audio END payload") from exc

        if "device_id" not in data:
            raise ValueError("Missing END field: device_id")
        if "session_id" not in data:
            raise ValueError("Missing END field: session_id")

        device_id = str(data["device_id"])
        session_id = str(data["session_id"])
        session = self.sessions.get(device_id)

        if session is None:
            raise ValueError(f"No active session for device: {device_id}")
        if session.session_id != session_id:
            raise ValueError(
                "END session_id does not match the active session"
            )
        if not session.buffer:
            raise ValueError("Audio session contains no PCM data")

        pcm_data = bytes(session.buffer)
        pcm_info = get_pcm_info(
            pcm_data=pcm_data,
            sample_rate=session.sample_rate,
            channels=session.channels,
            sample_width=session.sample_width,
        )
        wav_data = pcm_to_wav(
            pcm_data=pcm_data,
            sample_rate=session.sample_rate,
            channels=session.channels,
            sample_width=session.sample_width,
        )

        filename = f"{session.session_id}.wav"
        record = self.repository.save_bytes(
            payload=wav_data,
            filename=filename,
            audio_format="wav",
            metadata={
                "source": "esp32",
                "device_id": session.device_id,
                "session_id": session.session_id,
                "encoding": session.encoding,
                "packet_count": session.packet_count,
                "sample_rate": pcm_info.sample_rate,
                "channels": pcm_info.channels,
                "sample_width": pcm_info.sample_width,
                "frame_count": pcm_info.frame_count,
                "duration": pcm_info.duration,
            },
        )

        del self.sessions[device_id]

        if self.on_completed is not None:
            try:
                self.on_completed(record)
            except Exception:
                logger.exception(
                    "[AUDIO] Completed handler failed | device=%s | session=%s",
                    device_id,
                    session_id,
                )

        return record

    def cleanup_expired(self) -> list[str]:
        expired_devices = []
        for device_id, session in list(self.sessions.items()):
            if session.expired(self.session_timeout):
                expired_devices.append(device_id)
                del self.sessions[device_id]
        return expired_devices

    def has_active_session(self, device_id: str) -> bool:
        return device_id in self.sessions
