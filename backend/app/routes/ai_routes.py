from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request


ai_blueprint = Blueprint(
    "ai",
    __name__,
    url_prefix="/api/v1/ai",
)


def ok(data, message="OK", status=200):
    return jsonify(
        {
            "success": True,
            "data": data,
            "message": message,
        }
    ), status


def error(code, message, status):
    return jsonify(
        {
            "success": False,
            "error": {
                "code": code,
                "message": message,
            },
        }
    ), status


@ai_blueprint.post("/predict-file")
def predict_file():
    """
    Upload WAV -> AudioRepository -> VoiceCommandService -> AIService
    -> LIGHT ON/OFF -> MQTT.

    Endpoint này dùng cùng business pipeline với audio nhận từ ESP32.
    """
    upload = request.files.get("file") or request.files.get("audio")

    if upload is None:
        return error(
            "AI_FILE_REQUIRED",
            "Audio file is required",
            400,
        )

    filename = (upload.filename or "").strip()
    if not filename:
        return error(
            "AI_FILE_REQUIRED",
            "Audio filename is required",
            400,
        )

    if not filename.lower().endswith(".wav"):
        return error(
            "AI_FORMAT_INVALID",
            "AI voice command only supports WAV files",
            400,
        )

    settings = current_app.config["SETTINGS"]
    device_id = (
        request.form.get("device_id")
        or settings.device_id
        or ""
    ).strip()

    if not device_id:
        return error(
            "DEVICE_ID_REQUIRED",
            "device_id is required",
            400,
        )

    audio_service = current_app.extensions["audio_service"]
    voice_command_service = current_app.extensions[
        "voice_command_service"
    ]

    # 1) Lưu file WAV và để AudioService đọc metadata kỹ thuật
    #    như duration, sample_rate, channels, ...
    try:
        record = audio_service.save_upload(upload)
    except ValueError as exc:
        return error(
            "AUDIO_INVALID",
            str(exc),
            400,
        )
    except Exception:
        current_app.logger.exception(
            "Could not save AI test audio"
        )
        return error(
            "AUDIO_PROCESSING_FAILED",
            "Audio could not be processed",
            422,
        )

    audio_id = record["audio_id"]
    session_id = f"upload_{audio_id}"

    # 2) Bổ sung dữ liệu mà VoiceCommandService cần.
    record = audio_service.update_metadata(
        audio_id,
        {
            "source": "upload",
            "device_id": device_id,
            "session_id": session_id,
        },
    )

    if record is None:
        return error(
            "AUDIO_NOT_FOUND",
            "Saved audio record could not be loaded",
            500,
        )

    # 3) Chạy đúng shared pipeline.
    try:
        result = voice_command_service.process(record)
    except Exception:
        current_app.logger.exception(
            "Voice command processing failed for uploaded audio %s",
            audio_id,
        )
        return error(
            "VOICE_COMMAND_FAILED",
            "Voice command processing failed",
            500,
        )

    # 4) Lưu kết quả AI vào metadata để Audio Library / Cloud có thể đọc lại.
    updated_record = audio_service.update_metadata(
        audio_id,
        {
            "ai_ran": result.ai_ran,
            "ai_label": result.label,
            "ai_text": result.label,
            "ai_confidence": result.confidence,
            "ai_accepted": result.accepted,
            "ai_command": result.command,
            "ai_state": result.state,
            "ai_published": result.published,
            "ai_reason": result.reason,
        },
    )

    # 5) Đồng bộ metadata lên Cloud nếu Cloud đang được cấu hình.
    cloud_service = current_app.extensions.get("cloud_service")
    if cloud_service is not None and updated_record is not None:
        try:
            cloud_service.save_metadata(updated_record)
        except Exception:
            current_app.logger.warning(
                "Cloud metadata sync failed for AI upload %s",
                audio_id,
                exc_info=True,
            )

    # 6) Response phân biệt rõ:
    #    ai_ran=False => chưa có prediction, label/confidence null là hợp lệ.
    #    ai_ran=True  => AI đã chạy và label/confidence là prediction thật.
    return ok(
        {
            "audio_id": audio_id,
            "filename": filename,
            "device_id": device_id,
            "session_id": result.session_id,
            "duration": record.get("duration"),
            "ai_ran": result.ai_ran,
            "label": result.label,
            "confidence": result.confidence,
            "accepted": result.accepted,
            "command": result.command,
            "state": result.state,
            "published": result.published,
            "reason": result.reason,
        },
        "AI voice command completed",
        200,
    )