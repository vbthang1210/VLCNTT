from __future__ import annotations

import json
from pathlib import Path
from urllib import request

from ..storage import AudioRepository


class TTSNotConfigured(RuntimeError):
    pass


class TTSService:
    """Generate speech through an OpenAI-compatible HTTP endpoint."""

    def __init__(
        self,
        provider: str | None = None,
        repository: AudioRepository | None = None,
        api_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        default_voice: str | None = None,
        response_format: str = "mp3",
        opener=None,
    ):
        self.provider = provider
        self.repository = repository
        self.api_url = api_url
        self.api_key = api_key
        self.model = model
        self.default_voice = default_voice
        self.response_format = response_format
        self.opener = opener or request.urlopen

    def synthesize(self, text: str, voice: str | None = None) -> dict:
        if not isinstance(text, str) or not text.strip():
            raise ValueError("text is required")
        if self.provider != "openai_compatible" or not all(
            [self.repository, self.api_url, self.api_key, self.model]
        ):
            raise TTSNotConfigured("OpenAI-compatible TTS requires endpoint, key, model and storage")
        selected_voice = voice or self.default_voice
        if not selected_voice:
            raise TTSNotConfigured("TTS voice is not configured")
        if self.response_format not in {"mp3", "wav"}:
            raise TTSNotConfigured("TTS response format must be mp3 or wav")

        payload = json.dumps(
            {
                "model": self.model,
                "input": text.strip(),
                "voice": selected_voice,
                "response_format": self.response_format,
            }
        ).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        http_request = request.Request(self.api_url, data=payload, headers=headers, method="POST")
        with self.opener(http_request, timeout=15) as response:
            if getattr(response, "status", 200) < 200 or getattr(response, "status", 200) >= 300:
                raise RuntimeError("TTS provider request failed")
            audio_bytes = response.read()
        if not audio_bytes:
            raise RuntimeError("TTS provider returned empty audio")

        suffix = self.response_format
        filename = f"tts_{Path(self.api_url).name or 'audio'}.{suffix}"
        from io import BytesIO
        from werkzeug.datastructures import FileStorage

        upload = FileStorage(
            stream=BytesIO(audio_bytes),
            filename=filename,
            content_type="audio/mpeg" if suffix == "mp3" else "audio/wav",
        )
        record = self.repository.save_upload(upload)
        record["source"] = "tts"
        return record


__all__ = ["TTSNotConfigured", "TTSService"]
