from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    mqtt_enabled: bool
    mqtt_host: str
    mqtt_port: int
    mqtt_username: str | None
    mqtt_password: str | None
    device_id: str
    public_base_url: str
    storage_path: Path
    metadata_path: Path
    max_audio_size: int
    recording_default_seconds: int
    recording_max_seconds: int
    recording_session_timeout_seconds: int
    cors_origin: str
    tts_provider: str | None
    cloud_provider: str | None
    notification_provider: str | None
    tts_api_url: str | None
    tts_api_key: str | None
    tts_model: str | None
    tts_voice: str | None
    tts_response_format: str
    cloud_project_id: str | None
    cloud_access_token: str | None
    cloud_collection: str
    notification_project_id: str | None
    notification_access_token: str | None
    notification_device_token: str | None

    @classmethod
    def from_env(cls, overrides: dict | None = None) -> "Settings":
        values = dict(os.environ)
        values.update({k: str(v) for k, v in (overrides or {}).items()})
        root = Path(__file__).resolve().parents[1]
        storage = Path(values.get("AUDIO_STORAGE_PATH", str(root / "storage" / "audio")))
        metadata = Path(values.get("METADATA_PATH", str(root / "storage" / "metadata.json")))
        return cls(
            host=values.get("HOST", "127.0.0.1"),
            port=int(values.get("PORT", "8000")),
            mqtt_enabled=values.get("MQTT_ENABLED", "true").lower() in {"1", "true", "yes"},
            mqtt_host=values.get("MQTT_HOST", "127.0.0.1"),
            mqtt_port=int(values.get("MQTT_PORT", "1883")),
            mqtt_username=values.get("MQTT_USERNAME") or None,
            mqtt_password=values.get("MQTT_PASSWORD") or None,
            device_id=values.get("DEVICE_ID", "esp32_01"),
            public_base_url=values.get("PUBLIC_BASE_URL", "http://127.0.0.1:8000").rstrip("/"),
            storage_path=storage,
            metadata_path=metadata,
            max_audio_size=int(values.get("MAX_AUDIO_SIZE", str(20 * 1024 * 1024))),
            recording_default_seconds=int(values.get("RECORDING_DEFAULT_SECONDS", "1")),
            recording_max_seconds=int(values.get("RECORDING_MAX_SECONDS", "60")),
            recording_session_timeout_seconds=int(
                values.get("RECORDING_SESSION_TIMEOUT_SECONDS", "15")
            ),
            cors_origin=values.get("CORS_ORIGIN", "*"),
            tts_provider=values.get("TTS_PROVIDER") or None,
            cloud_provider=values.get("CLOUD_PROVIDER") or None,
            notification_provider=values.get("NOTIFICATION_PROVIDER") or None,
            tts_api_url=values.get("TTS_API_URL") or None,
            tts_api_key=values.get("TTS_API_KEY") or None,
            tts_model=values.get("TTS_MODEL") or None,
            tts_voice=values.get("TTS_VOICE") or None,
            tts_response_format=values.get("TTS_RESPONSE_FORMAT", "mp3"),
            cloud_project_id=values.get("CLOUD_PROJECT_ID") or None,
            cloud_access_token=values.get("CLOUD_ACCESS_TOKEN") or None,
            cloud_collection=values.get("CLOUD_COLLECTION", "audio_metadata"),
            notification_project_id=values.get("NOTIFICATION_PROJECT_ID") or None,
            notification_access_token=values.get("NOTIFICATION_ACCESS_TOKEN") or None,
            notification_device_token=values.get("NOTIFICATION_DEVICE_TOKEN") or None,
        )

    def ensure_directories(self) -> None:
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.metadata_path.parent.mkdir(parents=True, exist_ok=True)
