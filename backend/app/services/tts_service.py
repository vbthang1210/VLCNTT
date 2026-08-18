from __future__ import annotations

import asyncio
import json
from pathlib import Path
import tempfile
from urllib import request
from urllib.error import HTTPError
from urllib.parse import quote, urlencode

from ..storage import AudioRepository


class TTSNotConfigured(RuntimeError):
    pass


class TTSProviderError(RuntimeError):
    def __init__(self, status: int, provider_code: str | None, message: str):
        super().__init__(message)
        self.status = status
        self.provider_code = provider_code
        self.message = message


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
        edge_synthesizer=None,
    ):
        self.provider = provider
        self.repository = repository
        self.api_url = api_url
        self.api_key = api_key
        self.model = model or ("eleven_multilingual_v2" if provider == "elevenlabs" else None)
        self.default_voice = default_voice
        self.response_format = response_format
        self.opener = opener or request.urlopen
        self.edge_synthesizer = edge_synthesizer

    def synthesize(self, text: str, voice: str | None = None) -> dict:
        if not isinstance(text, str) or not text.strip():
            raise ValueError("text is required")
        if self.repository is None:
            raise TTSNotConfigured("TTS requires Backend audio storage")
        selected_voice = voice or self.default_voice
        if not selected_voice:
            raise TTSNotConfigured("TTS voice is not configured")
        if self.response_format not in {"mp3", "wav"}:
            raise TTSNotConfigured("TTS response format must be mp3 or wav")

        if self.provider == "edge":
            if self.response_format != "mp3":
                raise TTSNotConfigured("Edge TTS currently supports mp3 output only")
            audio_bytes = self._edge_synthesize(text.strip(), selected_voice)
            safe_voice = selected_voice.replace("/", "_")
            return self._save_audio(audio_bytes, "mp3", f"tts_edge_{safe_voice}.mp3")

        if not all([self.api_url, self.api_key, self.model]):
            raise TTSNotConfigured("TTS requires endpoint, key and model")
        if self.provider == "openai_compatible":
            endpoint, payload, headers = self._openai_request(text, selected_voice)
        elif self.provider == "elevenlabs":
            endpoint, payload, headers = self._elevenlabs_request(text, selected_voice)
        else:
            raise TTSNotConfigured("Unsupported TTS provider")

        http_request = request.Request(endpoint, data=payload, headers=headers, method="POST")
        try:
            with self.opener(http_request, timeout=15) as response:
                status = getattr(response, "status", 200)
                if status < 200 or status >= 300:
                    detail = response.read(512).decode("utf-8", errors="replace").strip()
                    raise self._provider_error(status, detail)
                audio_bytes = response.read()
        except HTTPError as exc:
            detail = exc.read(512).decode("utf-8", errors="replace").strip()
            raise self._provider_error(exc.code, detail) from exc
        if not audio_bytes:
            raise RuntimeError("TTS provider returned empty audio")

        suffix = self.response_format
        return self._save_audio(audio_bytes, suffix, f"tts_{Path(self.api_url).name or 'audio'}.{suffix}")

    def _save_audio(self, audio_bytes: bytes, suffix: str, filename: str) -> dict:
        if not audio_bytes:
            raise RuntimeError("TTS provider returned empty audio")
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

    def _edge_synthesize(self, text: str, voice: str) -> bytes:
        if self.edge_synthesizer is not None:
            return self.edge_synthesizer(text, voice)
        try:
            import edge_tts
        except ImportError as exc:
            raise TTSNotConfigured("Install the edge-tts package to use Edge TTS") from exc

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as output:
            output_path = Path(output.name)

        async def generate() -> None:
            communicator = edge_tts.Communicate(text, voice=voice)
            await communicator.save(str(output_path))

        try:
            asyncio.run(generate())
            return output_path.read_bytes()
        except Exception as exc:
            raise TTSProviderError(502, "edge_tts_failed", f"Edge TTS request failed: {exc}") from exc
        finally:
            output_path.unlink(missing_ok=True)

    @staticmethod
    def _provider_error(status: int, detail: str) -> TTSProviderError:
        provider_code = None
        message = detail or "TTS provider request failed"
        try:
            payload = json.loads(detail)
            provider_detail = payload.get("detail", payload) if isinstance(payload, dict) else {}
            if isinstance(provider_detail, dict):
                provider_code = provider_detail.get("code") or provider_detail.get("status")
                message = provider_detail.get("message") or message
        except (TypeError, json.JSONDecodeError):
            pass
        return TTSProviderError(status, provider_code, f"TTS provider HTTP {status}: {message}")

    def _openai_request(self, text: str, voice: str) -> tuple[str, bytes, dict[str, str]]:
        payload = json.dumps(
            {
                "model": self.model,
                "input": text.strip(),
                "voice": voice,
                "response_format": self.response_format,
            }
        ).encode("utf-8")
        return (
            self.api_url,
            payload,
            {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
        )

    def _elevenlabs_request(self, text: str, voice: str) -> tuple[str, bytes, dict[str, str]]:
        output_format = "mp3_44100_128" if self.response_format == "mp3" else "wav_44100"
        endpoint = f"{self.api_url.rstrip('/')}/{quote(voice, safe='')}"
        endpoint = f"{endpoint}?{urlencode({'output_format': output_format})}"
        payload = json.dumps({"text": text.strip(), "model_id": self.model}).encode("utf-8")
        return (
            endpoint,
            payload,
            {
                "Content-Type": "application/json",
                "Accept": "audio/mpeg" if self.response_format == "mp3" else "audio/wav",
                "xi-api-key": self.api_key,
            },
        )


__all__ = ["TTSNotConfigured", "TTSProviderError", "TTSService"]
