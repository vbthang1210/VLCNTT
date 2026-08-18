from __future__ import annotations

import json
from urllib import error, request


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

    # =========================================================
    # COMMON
    # =========================================================

    def _check_firestore_config(self) -> None:
        if (
            self.provider != "firestore"
            or not self.project_id
            or not self.access_token
        ):
            if self.provider:
                raise CloudNotConfigured(
                    "Firestore requires project ID and access token"
                )

            raise CloudNotConfigured(
                "Cloud provider is not configured"
            )

    def _collection_url(self) -> str:
        return (
            f"https://firestore.googleapis.com/v1/projects/"
            f"{self.project_id}"
            f"/databases/(default)/documents/"
            f"{self.collection}"
        )

    def _document_url(self, document_id: str) -> str:
        return f"{self._collection_url()}/{document_id}"

    def _request(
        self,
        method: str,
        url: str,
        payload: bytes | None = None,
    ) -> dict:
        http_request = request.Request(
            url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.access_token}",
            },
            method=method,
        )

        try:
            with self.opener(http_request, timeout=10) as response:
                status = getattr(response, "status", 200)

                if status < 200 or status >= 300:
                    raise RuntimeError(
                        f"Cloud metadata request failed with status {status}"
                    )

                raw = response.read()

        except error.HTTPError as exc:
            raise RuntimeError(
                f"Cloud metadata request failed with status {exc.code}"
            ) from exc

        except error.URLError as exc:
            raise RuntimeError(
                f"Cloud metadata request failed: {exc.reason}"
            ) from exc

        if not raw:
            return {}

        return json.loads(raw.decode("utf-8"))

    # =========================================================
    # FIRESTORE VALUE CONVERSION
    # =========================================================

    @staticmethod
    def _firestore_value_to_python(value: dict):
        """
        Convert one Firestore REST API typed value into
        a normal Python value.
        """

        if "stringValue" in value:
            return value["stringValue"]

        if "integerValue" in value:
            return int(value["integerValue"])

        if "doubleValue" in value:
            return float(value["doubleValue"])

        if "booleanValue" in value:
            return bool(value["booleanValue"])

        if "nullValue" in value:
            return None

        if "timestampValue" in value:
            return value["timestampValue"]

        if "arrayValue" in value:
            values = value["arrayValue"].get("values", [])
            return [
                CloudService._firestore_value_to_python(item)
                for item in values
            ]

        if "mapValue" in value:
            fields = value["mapValue"].get("fields", {})
            return {
                key: CloudService._firestore_value_to_python(field_value)
                for key, field_value in fields.items()
            }

        return None

    @classmethod
    def _firestore_document_to_python(cls, document: dict) -> dict:
        """
        Convert Firestore REST document:

        {
            "name": ".../audio_metadata/audio_123",
            "fields": {
                "filename": {
                    "stringValue": "test.mp3"
                },
                "duration": {
                    "doubleValue": 5.2
                }
            }
        }

        into:

        {
            "audio_id": "audio_123",
            "filename": "test.mp3",
            "duration": 5.2
        }
        """

        fields = document.get("fields", {})

        result = {
            key: cls._firestore_value_to_python(value)
            for key, value in fields.items()
        }

        # Firestore document ID is not necessarily stored
        # as a field, so recover it from the document name.
        name = document.get("name", "")

        if name:
            document_id = name.rstrip("/").split("/")[-1]

            if "audio_id" not in result:
                result["audio_id"] = document_id

        return result

    # =========================================================
    # SAVE METADATA
    # =========================================================

    def save_metadata(self, record: dict) -> dict:
        self._check_firestore_config()

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
            "size",
            "status",
            "device_id",
        }

        fields = {
            key: {"stringValue": str(value)}
            for key, value in record.items()
            if key in allowed and value is not None
        }

        for key in {"duration", "sample_rate", "size"} & fields.keys():
            value = record[key]

            fields[key] = (
                {"doubleValue": value}
                if key == "duration"
                else {"integerValue": str(value)}
            )

        payload = json.dumps(
            {"fields": fields}
        ).encode("utf-8")

        response = self._request(
            "PATCH",
            self._document_url(audio_id),
            payload,
        )

        return {
            **record,
            "cloud_synced": True,
        }

    # =========================================================
    # GET ONE METADATA DOCUMENT
    # =========================================================

    def get_metadata(self, audio_id: str) -> dict | None:
        """
        Get one audio metadata document from Firestore.
        """

        self._check_firestore_config()

        if not audio_id:
            raise ValueError("audio_id is required")

        try:
            document = self._request(
                "GET",
                self._document_url(audio_id),
            )

        except RuntimeError as exc:
            message = str(exc)

            if "404" in message:
                return None

            raise

        return self._firestore_document_to_python(document)

    # =========================================================
    # LIST ALL METADATA DOCUMENTS
    # =========================================================

    def list_metadata(self) -> list[dict]:
        """
        Get all audio metadata documents from Firestore.
        """

        self._check_firestore_config()

        documents: list[dict] = []
        page_token: str | None = None

        while True:
            url = self._collection_url()

            query = [
                "pageSize=100",
            ]

            if page_token:
                query.append(
                    f"pageToken={page_token}"
                )

            url = f"{url}?{'&'.join(query)}"

            response = self._request(
                "GET",
                url,
            )

            for document in response.get("documents", []):
                documents.append(
                    self._firestore_document_to_python(
                        document
                    )
                )

            page_token = response.get("nextPageToken")

            if not page_token:
                break

        return documents

    # =========================================================
    # DEVICE STATUS
    # =========================================================

    def save_status(self, status: dict) -> dict:
        self._check_firestore_config()

        document_id = status.get("device_id")

        if not document_id:
            raise ValueError("device_id is required")

        fields = {
            key: {"stringValue": str(value)}
            for key, value in status.items()
            if value is not None
            and isinstance(value, (str, int, float, bool))
        }

        payload = json.dumps(
            {"fields": fields}
        ).encode("utf-8")

        url = (
            f"https://firestore.googleapis.com/v1/projects/"
            f"{self.project_id}"
            f"/databases/(default)/documents/"
            f"device_status/{document_id}"
        )

        self._request(
            "PATCH",
            url,
            payload,
        )

        return {
            **status,
            "cloud_synced": True,
        }

    # =========================================================
    # NOTIFICATION
    # =========================================================

    def notify(self, event: dict) -> bool:
        return False