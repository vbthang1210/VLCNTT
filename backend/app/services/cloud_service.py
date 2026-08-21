from __future__ import annotations

import json
from urllib.parse import quote, urlencode
from urllib import request
from urllib.error import HTTPError


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

    def _send(self, http_request, operation: str) -> None:
        try:
            with self.opener(http_request, timeout=10) as response:
                status = getattr(response, "status", 200)
                if status < 200 or status >= 300:
                    detail = response.read(512).decode("utf-8", errors="replace").strip()
                    raise RuntimeError(f"Firestore {operation} HTTP {status}: {detail}")
        except HTTPError as exc:
            detail = exc.read(512).decode("utf-8", errors="replace").strip()
            raise RuntimeError(f"Firestore {operation} HTTP {exc.code}: {detail}") from exc

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
            "text",
            "ai_label",
            "ai_text",
            "ai_confidence",
        }
        fields = {key: {"stringValue": str(value)} for key, value in record.items() if key in allowed and value is not None}
        for key in {"duration", "ai_confidence", "sample_rate", "channels", "bits_per_sample", "sample_count", "size"} & fields.keys():
            value = record[key]
            fields[key] = {"doubleValue": float(value)} if key in {"duration", "ai_confidence"} else {"integerValue": str(value)}
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
        self._send(http_request, "metadata")
        return {**record, "cloud_synced": True}

    @staticmethod
    def _decode_firestore_value(value):
        if not isinstance(value, dict):
            return None
        if "stringValue" in value:
            return value["stringValue"]
        if "integerValue" in value:
            return int(value["integerValue"])
        if "doubleValue" in value:
            return float(value["doubleValue"])
        if "booleanValue" in value:
            return bool(value["booleanValue"])
        if "timestampValue" in value:
            return value["timestampValue"]
        if "nullValue" in value:
            return None
        if "mapValue" in value:
            fields = value["mapValue"].get("fields", {})
            return {key: CloudService._decode_firestore_value(item) for key, item in fields.items()}
        if "arrayValue" in value:
            values = value["arrayValue"].get("values", [])
            return [CloudService._decode_firestore_value(item) for item in values]
        return None

    def list_metadata(self) -> list[dict]:
        if self.provider != "firestore" or not self.project_id or not self.access_token:
            if self.provider:
                raise CloudNotConfigured("Firestore requires project ID and access token")
            return []

        base_url = (
            f"https://firestore.googleapis.com/v1/projects/{self.project_id}"
            f"/databases/(default)/documents/{self.collection}"
        )
        records = []
        page_token = None
        for _ in range(20):
            query = {"pageSize": "100"}
            if page_token:
                query["pageToken"] = page_token
            http_request = request.Request(
                f"{base_url}?{urlencode(query)}",
                headers={
                    "Authorization": f"Bearer {self.access_token}",
                },
                method="GET",
            )
            try:
                with self.opener(http_request, timeout=10) as response:
                    status = getattr(response, "status", 200)
                    body = response.read(4 * 1024 * 1024)
                    if status < 200 or status >= 300:
                        detail = body.decode("utf-8", errors="replace").strip()
                        raise RuntimeError(f"Firestore list metadata HTTP {status}: {detail}")
                    data = json.loads(body.decode("utf-8"))
            except HTTPError as exc:
                detail = exc.read(512).decode("utf-8", errors="replace").strip()
                raise RuntimeError(f"Firestore list metadata HTTP {exc.code}: {detail}") from exc
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise RuntimeError("Firestore list metadata response was invalid") from exc

            for document in data.get("documents", []):
                if not isinstance(document, dict):
                    continue
                fields = document.get("fields", {})
                record = {
                    key: self._decode_firestore_value(value)
                    for key, value in fields.items()
                }
                document_id = str(document.get("name", "")).rsplit("/", 1)[-1]
                record["audio_id"] = record.get("audio_id") or document_id
                record["cloud_synced"] = True
                records.append(record)

            page_token = data.get("nextPageToken")
            if not page_token:
                break
        return records

    def delete_metadata(self, audio_id: str) -> bool:
        if self.provider != "firestore" or not self.project_id or not self.access_token:
            if self.provider:
                raise CloudNotConfigured("Firestore requires project ID and access token")
            return False
        if not isinstance(audio_id, str) or not audio_id:
            raise ValueError("audio_id is required")
        url = (
            f"https://firestore.googleapis.com/v1/projects/{self.project_id}"
            f"/databases/(default)/documents/{self.collection}/{quote(audio_id, safe='')}"
        )
        http_request = request.Request(
            url,
            headers={"Authorization": f"Bearer {self.access_token}"},
            method="DELETE",
        )
        self._send(http_request, "delete metadata")
        return True

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
        self._send(http_request, "status")
        return {**status, "cloud_synced": True}

    def notify(self, event: dict) -> bool:
        return False
