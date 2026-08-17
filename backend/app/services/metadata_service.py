from __future__ import annotations


class MetadataService:
    """Cloud metadata boundary; local repository remains the dev source of truth."""

    def __init__(self, provider=None):
        self.provider = provider

    def save(self, record: dict) -> dict:
        # No external Cloud credentials are configured in development.
        return record

    def list(self) -> list[dict]:
        return []
