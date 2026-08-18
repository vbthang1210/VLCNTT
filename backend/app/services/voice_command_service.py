from __future__ import annotations

import logging
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
    """Convert AI keyword predictions into LIGHT commands for an ESP32."""

    LIGHT_STATES = {
        "bat": "ON",
        "tat": "OFF",
    }

    def __init__(
        self,
        ai_service,
        audio_repository,
        mqtt_service,
        device_state,
    ) -> None:
        self.ai_service = ai_service
        self.audio_repository = audio_repository
        self.mqtt_service = mqtt_service
        self.device_state = device_state

    def process(self, record: dict[str, Any]) -> VoiceCommandResult:
        device_id = str(record.get("device_id") or "")
        session_id = str(record.get("session_id") or "")
        audio_id = str(record.get("audio_id") or record.get("id") or "")

        if not device_id or not session_id or not audio_id:
            logger.error(
                "[VOICE] Invalid audio record | device=%s | session=%s | audio_id=%s",
                device_id,
                session_id,
                audio_id,
            )
            return VoiceCommandResult(
                device_id=device_id,
                session_id=session_id,
                label=None,
                confidence=None,
                accepted=False,
                command=None,
                state=None,
                published=False,
                reason="INVALID_AUDIO_RECORD",
            )

        try:
            audio_path = self.audio_repository.path_for(audio_id)
            prediction = self.ai_service.predict(str(audio_path))
        except AIUnavailable as exc:
            logger.warning(
                "[VOICE] AI unavailable | device=%s | session=%s | error=%s",
                device_id,
                session_id,
                exc,
            )
            return VoiceCommandResult(
                device_id=device_id,
                session_id=session_id,
                label=None,
                confidence=None,
                accepted=False,
                command=None,
                state=None,
                published=False,
                reason="AI_UNAVAILABLE",
            )
        except Exception:
            logger.exception(
                "[VOICE] AI inference failed | device=%s | session=%s",
                device_id,
                session_id,
            )
            return VoiceCommandResult(
                device_id=device_id,
                session_id=session_id,
                label=None,
                confidence=None,
                accepted=False,
                command=None,
                state=None,
                published=False,
                reason="AI_INFERENCE_FAILED",
            )

        logger.info(
            "[VOICE] Prediction | device=%s | session=%s | label=%s | confidence=%.4f | accepted=%s",
            device_id,
            session_id,
            prediction.label,
            prediction.confidence,
            prediction.accepted,
        )

        if not prediction.accepted:
            return VoiceCommandResult(
                device_id=device_id,
                session_id=session_id,
                label=prediction.label,
                confidence=prediction.confidence,
                accepted=False,
                command=None,
                state=None,
                published=False,
                reason="LOW_CONFIDENCE",
            )

        light_state = self.LIGHT_STATES.get(prediction.label)

        if light_state is None:
            return VoiceCommandResult(
                device_id=device_id,
                session_id=session_id,
                label=prediction.label,
                confidence=prediction.confidence,
                accepted=True,
                command=None,
                state=None,
                published=False,
                reason="NO_ACTION",
            )

        request_id = f"ai_{session_id}"
        payload = {
            "request_id": request_id,
            "command": "LIGHT",
            "state": light_state,
        }

        published = self.mqtt_service.publish_command(
            device_id,
            payload,
        )

        if not published:
            logger.warning(
                "[VOICE] LIGHT command was not published | device=%s | session=%s | state=%s",
                device_id,
                session_id,
                light_state,
            )
            return VoiceCommandResult(
                device_id=device_id,
                session_id=session_id,
                label=prediction.label,
                confidence=prediction.confidence,
                accepted=True,
                command="LIGHT",
                state=light_state,
                published=False,
                reason="MQTT_UNAVAILABLE",
            )

        self.device_state.set_current_request(
            device_id,
            request_id,
        )

        logger.info(
            "[VOICE] LIGHT command published | device=%s | session=%s | state=%s | request_id=%s",
            device_id,
            session_id,
            light_state,
            request_id,
        )

        return VoiceCommandResult(
            device_id=device_id,
            session_id=session_id,
            label=prediction.label,
            confidence=prediction.confidence,
            accepted=True,
            command="LIGHT",
            state=light_state,
            published=True,
            reason="PUBLISHED",
        )
