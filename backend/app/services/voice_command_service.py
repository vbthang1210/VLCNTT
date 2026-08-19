from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Any

from .ai_service import AIUnavailable

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class VoiceCommandResult:
    device_id: str
    session_id: str
    label: str | None
    confidence: float | None
    accepted: bool
    command: str | None
    state: str | None
    published: bool
    reason: str


class VoiceCommandService:
    LIGHT_STATES = {"bat": "ON", "tat": "OFF"}

    def __init__(self, ai_service, audio_repository, mqtt_service):
        self.ai_service = ai_service
        self.audio_repository = audio_repository
        self.mqtt_service = mqtt_service

    def process(self, record: dict[str, Any]) -> VoiceCommandResult:
        device_id = str(record.get("device_id") or "")
        audio_id = str(record.get("audio_id") or record.get("id") or "")
        session_id = str(
            record.get("session_id") or record.get("recording_id") or audio_id
        )
        if not device_id or not session_id or not audio_id:
            return self._result(record, "INVALID_AUDIO_RECORD")
        duration = record.get("duration")
        if duration is None:
            return self._result(record, "AI_WINDOW_INVALID")
        try:
            duration_value = float(duration)
        except (TypeError, ValueError, OverflowError):
            return self._result(record, "AI_WINDOW_INVALID")
        if (
            isinstance(duration, bool)
            or not math.isfinite(duration_value)
            or not 0.5 <= duration_value <= 1.5
        ):
            return self._result(record, "AI_WINDOW_INVALID")
        try:
            prediction = self.ai_service.predict(str(self.audio_repository.path_for(audio_id)))
        except AIUnavailable:
            return self._result(record, "AI_UNAVAILABLE")
        except Exception:
            logger.exception(
                "[VOICE] AI inference failed | device=%s | audio=%s",
                device_id,
                audio_id,
            )
            return self._result(record, "AI_INFERENCE_FAILED")
        if not prediction.accepted:
            return self._result(record, "LOW_CONFIDENCE", prediction)
        state = self.LIGHT_STATES.get(prediction.label)
        if state is None:
            return self._result(record, "NO_ACTION", prediction)
        payload = {
            "request_id": f"ai_{session_id}",
            "command": "LIGHT",
            "state": state,
        }
        published = self.mqtt_service.publish_command(device_id, payload)
        reason = "PUBLISHED" if published else "MQTT_UNAVAILABLE"
        return self._result(record, reason, prediction, state, published)

    @staticmethod
    def _result(record, reason, prediction=None, state=None, published=False):
        return VoiceCommandResult(
            device_id=str(record.get("device_id") or ""),
            session_id=str(
                record.get("session_id")
                or record.get("recording_id")
                or record.get("audio_id")
                or ""
            ),
            label=prediction.label if prediction else None,
            confidence=prediction.confidence if prediction else None,
            accepted=prediction.accepted if prediction else False,
            command="LIGHT" if state else None,
            state=state,
            published=published,
            reason=reason,
        )
