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
    ai_ran: bool = False


class VoiceCommandService:
    LIGHT_STATES = {
        "bat": "ON",
        "tat": "OFF",
    }

    def __init__(self, ai_service, audio_repository, mqtt_service):
        self.ai_service = ai_service
        self.audio_repository = audio_repository
        self.mqtt_service = mqtt_service

    def process(self, record: dict[str, Any]) -> VoiceCommandResult:
        device_id = str(record.get("device_id") or "")
        audio_id = str(record.get("audio_id") or record.get("id") or "")
        session_id = str(
            record.get("session_id")
            or record.get("recording_id")
            or audio_id
        )

        if not device_id or not session_id or not audio_id:
            return self._result(record, "INVALID_AUDIO_RECORD")

        duration = record.get("duration")
        if duration is None:
            logger.warning(
                "[VOICE] Missing duration | device=%s | audio=%s",
                device_id,
                audio_id,
            )
            return self._result(record, "AI_WINDOW_INVALID")

        try:
            duration_value = float(duration)
        except (TypeError, ValueError, OverflowError):
            logger.warning(
                "[VOICE] Invalid duration=%r | device=%s | audio=%s",
                duration,
                device_id,
                audio_id,
            )
            return self._result(record, "AI_WINDOW_INVALID")

        if (
            isinstance(duration, bool)
            or not math.isfinite(duration_value)
            or not 0.5 <= duration_value <= 1.5
        ):
            logger.info(
                "[VOICE] Audio outside AI window | duration=%.3f | device=%s | audio=%s",
                duration_value,
                device_id,
                audio_id,
            )
            return self._result(record, "AI_WINDOW_INVALID")

        audio_path = self.audio_repository.path_for(audio_id)

        try:
            prediction = self.ai_service.predict(str(audio_path))
        except AIUnavailable as exc:
            logger.warning(
                "[VOICE] AI unavailable | device=%s | audio=%s | error=%s",
                device_id,
                audio_id,
                exc,
            )
            return self._result(record, "AI_UNAVAILABLE")
        except Exception:
            logger.exception(
                "[VOICE] AI inference failed | device=%s | audio=%s",
                device_id,
                audio_id,
            )
            return self._result(record, "AI_INFERENCE_FAILED")

        logger.info(
            "[VOICE] AI prediction | device=%s | audio=%s | label=%s | confidence=%.4f | accepted=%s",
            device_id,
            audio_id,
            prediction.label,
            prediction.confidence,
            prediction.accepted,
        )

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

        return self._result(
            record,
            reason,
            prediction=prediction,
            state=state,
            published=published,
        )

    @staticmethod
    def _result(
        record: dict[str, Any],
        reason: str,
        prediction=None,
        state: str | None = None,
        published: bool = False,
    ) -> VoiceCommandResult:
        return VoiceCommandResult(
            device_id=str(record.get("device_id") or ""),
            session_id=str(
                record.get("session_id")
                or record.get("recording_id")
                or record.get("audio_id")
                or ""
            ),
            label=prediction.label if prediction is not None else None,
            confidence=(
                prediction.confidence
                if prediction is not None
                else None
            ),
            accepted=(
                prediction.accepted
                if prediction is not None
                else False
            ),
            command="LIGHT" if state is not None else None,
            state=state,
            published=published,
            reason=reason,
            ai_ran=prediction is not None,
        )