from __future__ import annotations

from ..storage import AudioRepository


class AudioService:
    """Business boundary for audio records and backend-owned audio files."""

    def __init__(self, repository: AudioRepository):
        self.repository = repository

    def list_audio(self) -> list[dict]:
        return self.repository.list()

    def get_audio(self, audio_id: str) -> dict | None:
        return self.repository.get(audio_id)

    def stream_path(self, audio_id: str):
        return self.repository.path_for(audio_id)

    def save_upload(self, upload):
        return self.repository.save_upload(upload)

    def delete_audio(self, audio_id: str):
        return self.repository.delete(audio_id)


__all__ = ["AudioService"]
