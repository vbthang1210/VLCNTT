from pathlib import Path

import pytest

from app.services.ai_service import PredictionResult
from app.services.voice_command_service import VoiceCommandService


class FakeAIService:
    def __init__(self, prediction: PredictionResult):
        self.prediction = prediction
        self.paths: list[str] = []

    def predict(self, audio_path: str) -> PredictionResult:
        self.paths.append(audio_path)
        return self.prediction


class FakeAudioRepository:
    def path_for(self, audio_id: str) -> Path:
        return Path("test_audio") / f"{audio_id}.wav"


class FakeMqttService:
    def __init__(self, publish_result: bool = True):
        self.publish_result = publish_result
        self.commands: list[tuple[str, dict]] = []

    def publish_command(self, device_id: str, payload: dict) -> bool:
        self.commands.append((device_id, dict(payload)))
        return self.publish_result


class FakeDeviceState:
    def __init__(self):
        self.current_requests: list[tuple[str, str]] = []

    def set_current_request(self, device_id: str, request_id: str) -> None:
        self.current_requests.append((device_id, request_id))


def record() -> dict:
    return {
        "audio_id": "voice_001",
        "device_id": "esp32_01",
        "session_id": "voice_001",
    }


def service_for(prediction: PredictionResult, publish_result: bool = True):
    ai = FakeAIService(prediction)
    mqtt = FakeMqttService(publish_result)
    state = FakeDeviceState()
    service = VoiceCommandService(
        ai_service=ai,
        audio_repository=FakeAudioRepository(),
        mqtt_service=mqtt,
        device_state=state,
    )
    return service, ai, mqtt, state


def prediction(label: str, confidence: float, accepted: bool) -> PredictionResult:
    return PredictionResult(
        label=label,
        confidence=confidence,
        accepted=accepted,
        model_version="test_model",
    )


def test_bat_publishes_light_on():
    service, ai, mqtt, state = service_for(
        prediction("bat", 0.95, True)
    )

    result = service.process(record())

    assert result.reason == "PUBLISHED"
    assert result.state == "ON"
    assert result.published is True
    assert mqtt.commands == [
        (
            "esp32_01",
            {
                "request_id": "ai_voice_001",
                "command": "LIGHT",
                "state": "ON",
            },
        )
    ]
    assert state.current_requests == [
        ("esp32_01", "ai_voice_001")
    ]
    assert ai.paths == [
        str(Path("test_audio") / "voice_001.wav")
    ]


def test_tat_publishes_light_off():
    service, _ai, mqtt, state = service_for(
        prediction("tat", 0.93, True)
    )

    result = service.process(record())

    assert result.reason == "PUBLISHED"
    assert result.state == "OFF"
    assert mqtt.commands[0][1]["command"] == "LIGHT"
    assert mqtt.commands[0][1]["state"] == "OFF"
    assert state.current_requests == [
        ("esp32_01", "ai_voice_001")
    ]


@pytest.mark.parametrize("label", ["unknown", "silence"])
def test_non_action_keywords_do_not_publish(label):
    service, _ai, mqtt, state = service_for(
        prediction(label, 0.99, True)
    )

    result = service.process(record())

    assert result.reason == "NO_ACTION"
    assert result.published is False
    assert mqtt.commands == []
    assert state.current_requests == []


def test_low_confidence_does_not_publish_even_for_bat():
    service, _ai, mqtt, state = service_for(
        prediction("bat", 0.60, False)
    )

    result = service.process(record())

    assert result.reason == "LOW_CONFIDENCE"
    assert result.published is False
    assert mqtt.commands == []
    assert state.current_requests == []


def test_failed_mqtt_publish_does_not_mark_request_current():
    service, _ai, mqtt, state = service_for(
        prediction("bat", 0.95, True),
        publish_result=False,
    )

    result = service.process(record())

    assert result.reason == "MQTT_UNAVAILABLE"
    assert result.published is False
    assert len(mqtt.commands) == 1
    assert state.current_requests == []
