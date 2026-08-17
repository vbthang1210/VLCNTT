from __future__ import annotations

import io
import wave
from dataclasses import dataclass


@dataclass(frozen=True)
class AudioInfo:
    sample_rate: int
    channels: int
    sample_width: int
    frame_count: int
    duration: float
    pcm_size: int


def validate_pcm(
    pcm_data: bytes,
    sample_rate: int,
    channels: int,
    sample_width: int,
) -> None:
    if not pcm_data:
        raise ValueError("PCM data is empty")

    if sample_rate <= 0:
        raise ValueError("Invalid sample rate")

    if channels <= 0:
        raise ValueError("Invalid channel count")

    if sample_width <= 0:
        raise ValueError("Invalid sample width")

    frame_size = channels * sample_width

    if len(pcm_data) % frame_size != 0:
        raise ValueError(
            "PCM data is not aligned with the audio frame size"
        )


def get_pcm_info(
    pcm_data: bytes,
    sample_rate: int,
    channels: int,
    sample_width: int,
) -> AudioInfo:
    validate_pcm(
        pcm_data,
        sample_rate,
        channels,
        sample_width,
    )

    frame_size = channels * sample_width
    frame_count = len(pcm_data) // frame_size
    duration = frame_count / sample_rate

    return AudioInfo(
        sample_rate=sample_rate,
        channels=channels,
        sample_width=sample_width,
        frame_count=frame_count,
        duration=duration,
        pcm_size=len(pcm_data),
    )


def pcm_to_wav(
    pcm_data: bytes,
    sample_rate: int,
    channels: int,
    sample_width: int,
) -> bytes:
    """
    Convert raw PCM bytes into a complete WAV file.

    Expected PCM format:
        - signed PCM
        - little endian
        - sample width defined by sample_width
    """

    validate_pcm(
        pcm_data,
        sample_rate,
        channels,
        sample_width,
    )

    buffer = io.BytesIO()

    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(sample_width)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm_data)

    return buffer.getvalue()


def inspect_wav(wav_data: bytes) -> AudioInfo:
    """
    Read metadata from a WAV byte stream.
    """

    if not wav_data:
        raise ValueError("WAV data is empty")

    buffer = io.BytesIO(wav_data)

    with wave.open(buffer, "rb") as wav_file:
        channels = wav_file.getnchannels()
        sample_width = wav_file.getsampwidth()
        sample_rate = wav_file.getframerate()
        frame_count = wav_file.getnframes()

    duration = frame_count / sample_rate

    return AudioInfo(
        sample_rate=sample_rate,
        channels=channels,
        sample_width=sample_width,
        frame_count=frame_count,
        duration=duration,
        pcm_size=frame_count * channels * sample_width,
    )


class AudioService:
    """
    High-level audio processing service.

    Repository được giữ ở đây để AudioService có thể trở thành
    tầng xử lý audio trung tâm khi pipeline AI được bổ sung.
    """

    def __init__(self, repository=None):
        self.repository = repository

    def pcm_to_wav(
        self,
        pcm_data: bytes,
        sample_rate: int,
        channels: int,
        sample_width: int,
    ) -> bytes:
        return pcm_to_wav(
            pcm_data=pcm_data,
            sample_rate=sample_rate,
            channels=channels,
            sample_width=sample_width,
        )

    def get_pcm_info(
        self,
        pcm_data: bytes,
        sample_rate: int,
        channels: int,
        sample_width: int,
    ) -> AudioInfo:
        return get_pcm_info(
            pcm_data=pcm_data,
            sample_rate=sample_rate,
            channels=channels,
            sample_width=sample_width,
        )

    def inspect_wav(
        self,
        wav_data: bytes,
    ) -> AudioInfo:
        return inspect_wav(wav_data)

    def validate_pcm(
        self,
        pcm_data: bytes,
        sample_rate: int,
        channels: int,
        sample_width: int,
    ) -> None:
        validate_pcm(
            pcm_data=pcm_data,
            sample_rate=sample_rate,
            channels=channels,
            sample_width=sample_width,
        )