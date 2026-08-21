from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request, send_file

from ..services.cloud_service import CloudNotConfigured
from ..services.tts_service import TTSNotConfigured, TTSProviderError


audio_blueprint = Blueprint("audio", __name__, url_prefix="/api/v1/audio")


def ok(data, message="OK", status=200):
    return jsonify({"success": True, "data": data, "message": message}), status


def error(code, message, status):
    return jsonify({"success": False, "error": {"code": code, "message": message}}), status


def merge_audio_records(local_records: list[dict], cloud_records: list[dict]) -> list[dict]:
    local_by_id = {
        record.get("audio_id"): record
        for record in local_records
        if record.get("audio_id")
    }
    merged = []
    cloud_ids = set()
    for cloud_record in cloud_records:
        audio_id = cloud_record.get("audio_id")
        if not audio_id:
            continue
        cloud_ids.add(audio_id)
        local_record = local_by_id.get(audio_id)
        if local_record is None:
            merged.append({**cloud_record, "local_available": False})
        else:
            merged.append({**local_record, **cloud_record, "local_available": True})
    merged.extend(record for record in local_records if record.get("audio_id") not in cloud_ids)
    return merged


@audio_blueprint.get("")
def list_audio():
    local_records = current_app.extensions["audio_service"].list_audio()
    cloud_service = current_app.extensions["cloud_service"]
    try:
        cloud_records = cloud_service.list_metadata()
    except (CloudNotConfigured, RuntimeError) as exc:
        current_app.logger.warning("Cloud metadata list unavailable: %s", exc)
        return ok(local_records, "Loaded local audio; Cloud metadata unavailable")
    if not cloud_records:
        return ok(local_records)
    local_ids = {
        record.get("audio_id")
        for record in local_records
        if record.get("audio_id")
    }
    available_cloud_records = []
    for cloud_record in cloud_records:
        audio_id = cloud_record.get("audio_id")
        if audio_id and audio_id not in local_ids:
            try:
                cloud_service.delete_metadata(audio_id)
            except (CloudNotConfigured, RuntimeError, ValueError, AttributeError) as exc:
                current_app.logger.warning("Stale Cloud metadata delete failed for %s: %s", audio_id, exc)
            continue
        available_cloud_records.append(cloud_record)
    return ok(merge_audio_records(local_records, available_cloud_records))


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
        local_record = {**record, "local_available": True}
        cloud_record = current_app.extensions["cloud_service"].save_metadata(record)
        record = {**local_record, **cloud_record, "local_available": True}
    except Exception:
        current_app.logger.warning("Cloud metadata sync failed for %s", record["audio_id"], exc_info=True)
        record = {**record, "cloud_synced": False, "local_available": True}
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
    except ValueError as exc:
        return error("TEXT_INVALID", str(exc), 400)
    except TTSNotConfigured as exc:
        return error("TTS_NOT_CONFIGURED", str(exc), 501)
    except TTSProviderError as exc:
        if exc.status == 402 or exc.provider_code == "paid_plan_required":
            return error(
                "TTS_PLAN_REQUIRED",
                "TTS provider requires an eligible plan or voice for API use",
                402,
            )
        if exc.provider_code == "invalid_api_key":
            return error("TTS_AUTH_FAILED", "TTS provider API key was rejected", 401)
        if exc.provider_code == "voice_not_found":
            return error("TTS_VOICE_NOT_FOUND", "TTS voice ID was not found", 400)
        return error("TTS_PROVIDER_FAILED", "TTS provider request failed", 502)
    except Exception as exc:
        current_app.logger.warning("TTS provider request failed: %s", exc)
        return error("TTS_PROVIDER_FAILED", "TTS provider request failed", 502)
    try:
        cloud_record = current_app.extensions["cloud_service"].save_metadata(record)
        record = {**record, **cloud_record}
    except Exception:
        current_app.logger.warning("Cloud metadata sync failed for TTS %s", record["audio_id"], exc_info=True)
        record = {**record, "cloud_synced": False}
        return ok(record, "TTS generated locally; Cloud sync pending", 201)
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
