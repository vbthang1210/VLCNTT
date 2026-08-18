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
    MetadataService,
    NotificationService,
    TTSService,
)


def create_app(overrides: dict | None = None) -> Flask:
    """
    Create and configure the Flask application.

    The application is responsible for:

    - HTTP API
    - Audio storage
    - Audio streaming from ESP32
    - AI keyword inference
    - MQTT communication
    - Device state management
    - Cloud metadata
    - Notifications
    - Text-to-speech
    """

    # =========================================================
    # SETTINGS
    # =========================================================

    settings = Settings.from_env(overrides or {})
    settings.ensure_directories()

    # =========================================================
    # FLASK APPLICATION
    # =========================================================

    app = Flask(__name__)

    app.config["SETTINGS"] = settings

    app.config["TESTING"] = (
        str(
            (overrides or {}).get(
                "TESTING",
                "false",
            )
        ).lower()
        == "true"
    )

    # =========================================================
    # STORAGE
    # =========================================================

    repository = AudioRepository(
        settings.storage_path,
        settings.metadata_path,
        settings.max_audio_size,
    )

    app.extensions["audio_repository"] = repository

    # =========================================================
    # AUDIO SERVICES
    # =========================================================

    app.extensions["audio_service"] = AudioService(
        repository
    )

    app.extensions["audio_stream_service"] = AudioStreamService(
        repository
    )

    # =========================================================
    # METADATA / CLOUD
    # =========================================================

    app.extensions["metadata_service"] = MetadataService(
        settings.cloud_provider
    )

    app.extensions["cloud_service"] = CloudService(
        settings.cloud_provider,
        settings.cloud_project_id,
        settings.cloud_access_token,
        settings.cloud_collection,
    )

    # =========================================================
    # NOTIFICATION
    # =========================================================

    app.extensions["notification_service"] = NotificationService(
        settings.notification_provider,
        settings.notification_project_id,
        settings.notification_access_token,
        settings.notification_device_token,
    )

    # =========================================================
    # TEXT TO SPEECH
    # =========================================================

    app.extensions["tts_service"] = TTSService(
        settings.tts_provider,
        repository,
        settings.tts_api_url,
        settings.tts_api_key,
        settings.tts_model,
        settings.tts_voice,
        settings.tts_response_format,
    )

    # =========================================================
    # AI KEYWORD MODEL
    # =========================================================

    # AIService intentionally does not crash the whole backend when the
    # checkpoint is missing or invalid. Its ready/error state is exposed
    # through /health and inference will reject requests until it is ready.
    app.extensions["ai_service"] = AIService()

    # =========================================================
    # DEVICE STATE
    # =========================================================

    app.extensions["device_state"] = DeviceStateStore()

    # =========================================================
    # MQTT
    # =========================================================

    app.extensions["mqtt_service"] = MqttService(
        settings=settings,
        device_state=app.extensions["device_state"],
        notification_service=app.extensions[
            "notification_service"
        ],
        cloud_service=app.extensions[
            "cloud_service"
        ],
        audio_stream_service=app.extensions[
            "audio_stream_service"
        ],
    )

    # =========================================================
    # ROUTES
    # =========================================================

    app.register_blueprint(audio_blueprint)
    app.register_blueprint(device_blueprint)

    # =========================================================
    # CORS
    # =========================================================

    @app.after_request
    def add_cors(response):
        response.headers[
            "Access-Control-Allow-Origin"
        ] = settings.cors_origin

        response.headers[
            "Access-Control-Allow-Headers"
        ] = "Content-Type"

        response.headers[
            "Access-Control-Allow-Methods"
        ] = "GET,POST,OPTIONS"

        return response

    # =========================================================
    # HEALTH CHECK
    # =========================================================

    @app.get("/health")
    def health():
        mqtt = app.extensions["mqtt_service"]
        ai = app.extensions["ai_service"]
        ai_status = ai.status()

        return {
            "success": True,
            "data": {
                "service": "backend",
                "mqtt_connected": mqtt.is_connected(),
                "ai_ready": ai_status["ready"],
                "ai_device": ai_status["device"],
                "ai_model_version": ai_status["model_version"],
                "ai_error_code": ai_status["error_code"],
            },
            "message": "OK",
        }

    # =========================================================
    # START MQTT
    # =========================================================

    if (
        settings.mqtt_enabled
        and not app.config["TESTING"]
    ):
        app.extensions["mqtt_service"].start()

    return app
