from __future__ import annotations

from pathlib import Path


class AudioStreamService:
    """Small boundary for resolving backend-owned stream files."""

    def __init__(self, repository):
        self.repository = repository

    def resolve(self, audio_id: str) -> Path:
        path = self.repository.path_for(audio_id)
        if not path.is_file():
            raise FileNotFoundError(audio_id)
        return path
