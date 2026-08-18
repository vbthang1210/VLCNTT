from __future__ import annotations

import secrets

from flask import Blueprint, current_app, jsonify, request


device_blueprint = Blueprint("device", __name__, url_prefix="/api/v1/devices")


def ok(data, message="OK", status=200):
    return jsonify({"success": True, "data": data, "message": message}), status


def error(code, message, status):
    return jsonify({"success": False, "error": {"code": code, "message": message}}), status


def request_id_from_body(body: dict) -> str:
    value = body.get("request_id")
    return value if isinstance(value, str) and value else f"req_{secrets.token_hex(4)}"


def publish(device_id: str, payload: dict):
    service = current_app.extensions["mqtt_service"]
    state_store = current_app.extensions["device_state"]
    if not service.publish_command(device_id, payload):
        return error("MQTT_UNAVAILABLE", "MQTT command could not be published", 503)
    state_store.set_current_request(device_id, payload["request_id"])
    data = {"request_id": payload["request_id"], "command": payload["command"]}
    for key in ("recording_id", "duration_seconds"):
        if key in payload:
            data[key] = payload[key]
    return ok(data, "Command accepted", 202)


@device_blueprint.get("/<device_id>/status")
def get_status(device_id):
    state = current_app.extensions["device_state"].get(device_id)
    return ok(current_app.extensions["device_state"].as_dict(state))


@device_blueprint.post("/<device_id>/play")
def play(device_id):
    body = request.get_json(silent=True) or {}
    audio_id = body.get("audio_id")
    if not isinstance(audio_id, str) or not audio_id:
        return error("AUDIO_ID_REQUIRED", "audio_id is required", 400)
    record = current_app.extensions["audio_service"].get_audio(audio_id)
    if not record:
        return error("AUDIO_NOT_FOUND", "Audio file not found", 404)
    settings = current_app.config["SETTINGS"]
    payload = {
        "request_id": request_id_from_body(body),
        "command": "PLAY",
        "audio_id": audio_id,
        "audio_url": f"{settings.public_base_url}/api/v1/audio/{audio_id}/stream?format={record['format']}",
        "format": record["format"],
    }
    return publish(device_id, payload)


@device_blueprint.post("/<device_id>/stop")
def stop(device_id):
    body = request.get_json(silent=True) or {}
    return publish(device_id, {"request_id": request_id_from_body(body), "command": "STOP"})


@device_blueprint.post("/<device_id>/pause")
def pause(device_id):
    body = request.get_json(silent=True) or {}
    return publish(device_id, {"request_id": request_id_from_body(body), "command": "PAUSE"})


@device_blueprint.post("/<device_id>/volume")
def volume(device_id):
    body = request.get_json(silent=True) or {}
    value = body.get("volume")
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 100:
        return error("VOLUME_INVALID", "volume must be an integer from 0 to 100", 400)
    return publish(
        device_id,
        {"request_id": request_id_from_body(body), "command": "SET_VOLUME", "volume": value},
    )


@device_blueprint.post("/<device_id>/record/start")
def start_recording(device_id):
    body = request.get_json(silent=True) or {}
    settings = current_app.config["SETTINGS"]
    duration = body.get("duration_seconds", settings.recording_default_seconds)
    if (isinstance(duration, bool) or not isinstance(duration, int)
            or not 1 <= duration <= settings.recording_max_seconds):
        return error(
            "RECORDING_DURATION_INVALID",
            f"duration_seconds must be an integer from 1 to {settings.recording_max_seconds}",
            400,
        )
    recording_id = f"rec_{secrets.token_hex(4)}"
    return publish(
        device_id,
        {
            "request_id": request_id_from_body(body),
            "command": "START_RECORDING",
            "recording_id": recording_id,
            "duration_seconds": duration,
        },
    )


@device_blueprint.post("/<device_id>/record/stop")
def stop_recording(device_id):
    body = request.get_json(silent=True) or {}
    payload = {"request_id": request_id_from_body(body), "command": "STOP_RECORDING"}
    if isinstance(body.get("recording_id"), str) and body["recording_id"]:
        payload["recording_id"] = body["recording_id"]
    return publish(device_id, payload)
