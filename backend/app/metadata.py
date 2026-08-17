from __future__ import annotations

import json
import shutil
import subprocess
import wave
from pathlib import Path


ALLOWED_FORMATS = {"mp3", "wav"}
ALLOWED_MIME_TYPES = {
    "audio/mpeg",
    "audio/mp3",
    "audio/wav",
    "audio/x-wav",
    "audio/wave",
    "application/octet-stream",
}


def extension_for(filename: str) -> str:
    suffix = Path(filename).suffix.lower().lstrip(".")
    if suffix not in ALLOWED_FORMATS:
        raise ValueError("Only .mp3 and .wav audio files are supported")
    return suffix


def validate_mime(content_type: str | None) -> None:
    if content_type and content_type.lower() not in ALLOWED_MIME_TYPES:
        raise ValueError("Unsupported audio MIME type")


def extract_metadata(path: Path, audio_format: str) -> dict:
    if audio_format == "wav":
        with wave.open(str(path), "rb") as handle:
            sample_rate = handle.getframerate()
            frames = handle.getnframes()
            duration = frames / sample_rate if sample_rate else None
            return {
                "duration": duration,
                "sample_rate": sample_rate,
                "channels": handle.getnchannels(),
                "bits_per_sample": handle.getsampwidth() * 8,
            }

    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return {"duration": None, "sample_rate": None, "channels": None}
    result = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration:stream=sample_rate,channels",
            "-of",
            "json",
            str(path),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.returncode != 0:
        raise ValueError("Audio file could not be decoded")
    data = json.loads(result.stdout or "{}")
    stream = (data.get("streams") or [{}])[0]
    duration = (data.get("format") or {}).get("duration")
    return {
        "duration": float(duration) if duration is not None else None,
        "sample_rate": int(stream["sample_rate"]) if stream.get("sample_rate") else None,
        "channels": int(stream["channels"]) if stream.get("channels") else None,
    }
