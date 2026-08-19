import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

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


def record() -> dict:
    return {
        "audio_id": "voice_001",
        "recording_id": "voice_001",
        "device_id": "esp32_01",
        "duration": 1.0,
    }


def service_for(prediction: PredictionResult, publish_result: bool = True):
    ai = FakeAIService(prediction)
    mqtt = FakeMqttService(publish_result)
    service = VoiceCommandService(ai, FakeAudioRepository(), mqtt)
    return service, ai, mqtt


def prediction(label: str, confidence: float, accepted: bool) -> PredictionResult:
    return PredictionResult(label, confidence, accepted, "test_model")


def test_bat_publishes_light_on():
    service, ai, mqtt = service_for(prediction("bat", 0.95, True))

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
    assert ai.paths == [str(Path("test_audio") / "voice_001.wav")]


def test_tat_publishes_light_off():
    service, _ai, mqtt = service_for(prediction("tat", 0.93, True))

    result = service.process(record())

    assert result.reason == "PUBLISHED"
    assert result.state == "OFF"
    assert mqtt.commands[0][1]["command"] == "LIGHT"
    assert mqtt.commands[0][1]["state"] == "OFF"


def test_non_action_keywords_do_not_publish():
    service, _ai, mqtt = service_for(prediction("unknown", 0.99, True))

    result = service.process(record())

    assert result.reason == "NO_ACTION"
    assert result.published is False
    assert mqtt.commands == []


def test_low_confidence_does_not_publish():
    service, _ai, mqtt = service_for(prediction("bat", 0.60, False))

    result = service.process(record())

    assert result.reason == "LOW_CONFIDENCE"
    assert result.published is False
    assert mqtt.commands == []


def test_failed_mqtt_publish_returns_unavailable():
    service, _ai, mqtt = service_for(prediction("bat", 0.95, True), publish_result=False)

    result = service.process(record())

    assert result.reason == "MQTT_UNAVAILABLE"
    assert result.published is False
    assert len(mqtt.commands) == 1


def test_long_recording_is_not_sent_to_one_second_keyword_model():
    service, ai, mqtt = service_for(prediction("bat", 0.95, True))
    record_data = {**record(), "duration": 20.0}

    result = service.process(record_data)

    assert result.reason == "AI_WINDOW_INVALID"
    assert ai.paths == []
    assert mqtt.commands == []


def test_invalid_recording_duration_is_rejected_without_inference():
    service, ai, mqtt = service_for(prediction("bat", 0.95, True))
    record_data = {**record(), "duration": "not-a-number"}

    result = service.process(record_data)

    assert result.reason == "AI_WINDOW_INVALID"
    assert ai.paths == []
    assert mqtt.commands == []


def test_missing_recording_duration_is_rejected_without_inference():
    service, ai, mqtt = service_for(prediction("bat", 0.95, True))
    record_data = record()
    record_data.pop("duration")

    result = service.process(record_data)

    assert result.reason == "AI_WINDOW_INVALID"
    assert ai.paths == []
    assert mqtt.commands == []


def test_overflowing_recording_duration_is_rejected_without_inference():
    service, ai, mqtt = service_for(prediction("bat", 0.95, True))
    record_data = {**record(), "duration": 10**1000}

    result = service.process(record_data)

    assert result.reason == "AI_WINDOW_INVALID"
    assert ai.paths == []
    assert mqtt.commands == []
