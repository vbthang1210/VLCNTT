from __future__ import annotations

import json
from urllib import request


class CloudNotConfigured(RuntimeError):
    pass


class CloudService:
    """Firestore REST adapter for light metadata only; audio stays in Backend storage."""

    def __init__(
        self,
        provider: str | None = None,
        project_id: str | None = None,
        access_token: str | None = None,
        collection: str = "audio_metadata",
        opener=None,
    ):
        self.provider = provider
        self.project_id = project_id
        self.access_token = access_token
        self.collection = collection
        self.opener = opener or request.urlopen

    def save_metadata(self, record: dict) -> dict:
        if self.provider != "firestore" or not self.project_id or not self.access_token:
            if self.provider:
                raise CloudNotConfigured("Firestore requires project ID and access token")
            return {**record, "cloud_synced": False}
        audio_id = record.get("audio_id") or record.get("id")
        if not audio_id:
            raise ValueError("audio_id is required")
        allowed = {
            "audio_id",
            "filename",
            "original_filename",
            "duration",
            "format",
            "sample_rate",
            "channels",
            "bits_per_sample",
            "sample_count",
            "size",
            "status",
            "device_id",
            "source",
        }
        fields = {key: {"stringValue": str(value)} for key, value in record.items() if key in allowed and value is not None}
        for key in {"duration", "sample_rate", "channels", "bits_per_sample", "sample_count", "size"} & fields.keys():
            value = record[key]
            fields[key] = {"doubleValue": value} if key == "duration" else {"integerValue": str(value)}
        payload = json.dumps({"fields": fields}).encode("utf-8")
        url = (
            f"https://firestore.googleapis.com/v1/projects/{self.project_id}"
            f"/databases/(default)/documents/{self.collection}/{audio_id}"
        )
        http_request = request.Request(
            url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.access_token}",
            },
            method="PATCH",
        )
        with self.opener(http_request, timeout=10) as response:
            if getattr(response, "status", 200) < 200 or getattr(response, "status", 200) >= 300:
                raise RuntimeError("Cloud metadata request failed")
        return {**record, "cloud_synced": True}

    def save_status(self, status: dict) -> dict:
        if self.provider != "firestore" or not self.project_id or not self.access_token:
            if self.provider:
                raise CloudNotConfigured("Firestore requires project ID and access token")
            return {**status, "cloud_synced": False}
        document_id = status.get("device_id")
        if not document_id:
            raise ValueError("device_id is required")
        fields = {
            key: {"stringValue": str(value)}
            for key, value in status.items()
            if value is not None and isinstance(value, (str, int, float, bool))
        }
        payload = json.dumps({"fields": fields}).encode("utf-8")
        url = (
            f"https://firestore.googleapis.com/v1/projects/{self.project_id}"
            f"/databases/(default)/documents/device_status/{document_id}"
        )
        http_request = request.Request(
            url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.access_token}",
            },
            method="PATCH",
        )
        with self.opener(http_request, timeout=10) as response:
            if getattr(response, "status", 200) < 200 or getattr(response, "status", 200) >= 300:
                raise RuntimeError("Cloud status request failed")
        return {**status, "cloud_synced": True}

    def notify(self, event: dict) -> bool:
        return False
