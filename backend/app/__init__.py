from __future__ import annotations

from flask import Flask

from .config import Settings
from .mqtt_service import DeviceStateStore, MqttService
from .storage import AudioRepository
from .routes.audio_routes import audio_blueprint
from .routes.device_routes import device_blueprint
from .services import (
    AIService,
    AudioService,
    AudioStreamService,
    CloudService,
    NotificationService,
    PcmRecordingService,
    TTSService,
    VoiceCommandService,
)


def create_app(overrides: dict | None = None) -> Flask:
    settings = Settings.from_env(overrides or {})
    settings.ensure_directories()

    app = Flask(__name__)
    app.config["SETTINGS"] = settings
    app.config["TESTING"] = str((overrides or {}).get("TESTING", "false")).lower() == "true"
    repository = AudioRepository(
        settings.storage_path,
        settings.metadata_path,
        settings.max_audio_size,
    )
    app.extensions["audio_repository"] = repository
    app.extensions["audio_service"] = AudioService(repository)
    app.extensions["audio_stream_service"] = AudioStreamService(repository)
    app.extensions["recording_service"] = PcmRecordingService(
        repository,
        settings.recording_max_seconds,
        settings.recording_session_timeout_seconds,
    )
    app.extensions["ai_service"] = AIService()
    app.extensions["cloud_service"] = CloudService(
        settings.cloud_provider,
        settings.cloud_project_id,
        settings.cloud_access_token,
        settings.cloud_collection,
    )
    app.extensions["notification_service"] = NotificationService(
        settings.notification_provider,
        settings.notification_project_id,
        settings.notification_access_token,
        settings.notification_device_token,
    )
    app.extensions["tts_service"] = TTSService(
        settings.tts_provider,
        repository,
        settings.tts_api_url,
        settings.tts_api_key,
        settings.tts_model,
        settings.tts_voice,
        settings.tts_response_format,
    )
    app.extensions["device_state"] = DeviceStateStore()
    app.extensions["mqtt_service"] = MqttService(
        settings,
        app.extensions["device_state"],
        app.extensions["notification_service"],
        app.extensions["cloud_service"],
        app.extensions["recording_service"],
    )
    app.extensions["voice_command_service"] = VoiceCommandService(
        app.extensions["ai_service"],
        repository,
        app.extensions["mqtt_service"],
    )
    app.extensions["mqtt_service"].set_voice_command_service(
        app.extensions["voice_command_service"]
    )

    app.register_blueprint(audio_blueprint)
    app.register_blueprint(device_blueprint)

    @app.after_request
    def add_cors(response):
        response.headers["Access-Control-Allow-Origin"] = settings.cors_origin
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        response.headers["Access-Control-Allow-Methods"] = "GET,POST,DELETE,OPTIONS"
        return response

    @app.get("/health")
    def health():
        mqtt = app.extensions["mqtt_service"]
        ai = app.extensions["ai_service"].status()
        return {
            "success": True,
            "data": {
                "service": "backend",
                "mqtt_connected": mqtt.is_connected(),
                "ai_ready": ai["ready"],
                "ai_device": ai["device"],
                "ai_model_version": ai["model_version"],
                "ai_error_code": ai["error_code"],
            },
            "message": "OK",
        }

    if settings.mqtt_enabled and not app.config["TESTING"]:
        app.extensions["mqtt_service"].start()

    return app
