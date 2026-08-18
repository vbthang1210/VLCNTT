from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request, send_file


audio_blueprint = Blueprint("audio", __name__, url_prefix="/api/v1/audio")


def ok(data, message="OK", status=200):
    return jsonify({"success": True, "data": data, "message": message}), status


def error(code, message, status):
    return jsonify({"success": False, "error": {"code": code, "message": message}}), status


@audio_blueprint.get("")
def list_audio():
    return ok(current_app.extensions["audio_service"].list_audio())


@audio_blueprint.get("/<audio_id>")
def get_audio(audio_id):
    record = current_app.extensions["audio_service"].get_audio(audio_id)
    if not record:
        return error("AUDIO_NOT_FOUND", "Audio file not found", 404)
    return ok(record)


@audio_blueprint.delete("/<audio_id>")
def delete_audio(audio_id):
    try:
        record = current_app.extensions["audio_service"].delete_audio(audio_id)
    except (OSError, RuntimeError):
        return error("AUDIO_DELETE_FAILED", "Audio file could not be deleted", 500)
    if not record:
        return error("AUDIO_NOT_FOUND", "Audio file not found", 404)
    return ok(record, "Audio deleted")


@audio_blueprint.post("/upload")
def upload_audio():
    upload = request.files.get("file") or request.files.get("audio")
    if upload is None:
        return error("AUDIO_FILE_REQUIRED", "Audio file is required", 400)
    try:
        record = current_app.extensions["audio_service"].save_upload(upload)
    except ValueError as exc:
        return error("AUDIO_INVALID", str(exc), 400)
    except Exception:
        return error("AUDIO_PROCESSING_FAILED", "Audio could not be processed", 422)
    try:
        record = current_app.extensions["cloud_service"].save_metadata(record)
    except Exception:
        current_app.logger.warning("Cloud metadata sync failed for %s", record["audio_id"])
        record = {**record, "cloud_synced": False}
        return ok(record, "Audio uploaded locally; Cloud sync pending", 201)
    return ok(record, "Audio uploaded", 201)


@audio_blueprint.post("/tts")
def tts_audio():
    body = request.get_json(silent=True) or {}
    text = body.get("text")
    if not isinstance(text, str) or not text.strip():
        return error("TEXT_REQUIRED", "text is required", 400)
    try:
        record = current_app.extensions["tts_service"].synthesize(text, body.get("voice"))
        cloud_record = current_app.extensions["cloud_service"].save_metadata(record)
        record = {**record, **cloud_record}
    except ValueError as exc:
        return error("TEXT_INVALID", str(exc), 400)
    except Exception as exc:
        return error("TTS_NOT_CONFIGURED", str(exc), 501)
    return ok(record, "TTS generated", 201)


@audio_blueprint.get("/<audio_id>/stream")
def stream_audio(audio_id):
    audio_service = current_app.extensions["audio_service"]
    stream_service = current_app.extensions["audio_stream_service"]
    record = audio_service.get_audio(audio_id)
    if not record:
        return error("AUDIO_NOT_FOUND", "Audio file not found", 404)
    try:
        path = stream_service.resolve(audio_id)
    except (FileNotFoundError, RuntimeError):
        return error("AUDIO_NOT_FOUND", "Audio file not found", 404)
    if not path.is_file():
        return error("AUDIO_NOT_FOUND", "Audio file not found", 404)
    mimetype = "audio/mpeg" if record["format"] == "mp3" else "audio/wav"
    return send_file(path, mimetype=mimetype, conditional=True, download_name=record["filename"])


@audio_blueprint.get("/<audio_id>/download")
def download_audio(audio_id):
    audio_service = current_app.extensions["audio_service"]
    stream_service = current_app.extensions["audio_stream_service"]
    record = audio_service.get_audio(audio_id)
    if not record:
        return error("AUDIO_NOT_FOUND", "Audio file not found", 404)
    try:
        path = stream_service.resolve(audio_id)
    except (FileNotFoundError, RuntimeError):
        return error("AUDIO_NOT_FOUND", "Audio file not found", 404)
    if not path.is_file():
        return error("AUDIO_NOT_FOUND", "Audio file not found", 404)
    mimetype = "audio/mpeg" if record["format"] == "mp3" else "audio/wav"
    return send_file(
        path,
        mimetype=mimetype,
        conditional=True,
        as_attachment=True,
        download_name=record["filename"],
    )
