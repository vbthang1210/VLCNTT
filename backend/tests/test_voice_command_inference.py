from pathlib import Path
import random
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.ai_service import AIService
from app.services.voice_command_service import VoiceCommandService


# ============================================================
# Paths
# ============================================================

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_DIR.parent

DATASET_DIR = PROJECT_ROOT / "dataset" / "processed"


# ============================================================
# Fake Audio Repository
# ============================================================

class FakeAudioRepository:
    """
    VoiceCommandService cần:
        audio_repository.path_for(audio_id)

    Ta không dùng storage thật ở test này.
    Thay vào đó luôn trả về file WAV ngẫu nhiên đã chọn.
    """

    def __init__(self, audio_path: Path):
        self.audio_path = audio_path

    def path_for(self, audio_id: str) -> Path:
        return self.audio_path


# ============================================================
# Fake MQTT
# ============================================================

class FakeMqttService:
    """
    Không publish thật lên Mosquitto.

    Chỉ lưu lại command mà VoiceCommandService muốn gửi.
    """

    def __init__(self):
        self.commands = []

    def publish_command(self, device_id: str, payload: dict) -> bool:

        self.commands.append(
            {
                "device_id": device_id,
                "payload": dict(payload),
            }
        )

        # Giả sử MQTT publish thành công
        return True


# ============================================================
# Random audio
# ============================================================

def get_random_action_audio() -> Path:
    """
    Chỉ lấy class có action:
        bat
        tat

    Không lấy silence/unknown vì chúng không tạo LIGHT command.
    """

    audio_files = []

    for label in ["bat", "tat"]:
        class_dir = DATASET_DIR / label

        audio_files.extend(
            class_dir.rglob("*.wav")
        )

    audio_files = list(audio_files)

    if not audio_files:
        raise RuntimeError(
            f"No bat/tat WAV files found in: {DATASET_DIR}"
        )

    return random.choice(audio_files)


# ============================================================
# Main test
# ============================================================

def main():

    print("=" * 70)
    print("VOICE COMMAND INFERENCE TEST")
    print("=" * 70)

    # --------------------------------------------------------
    # Pick random audio
    # --------------------------------------------------------

    audio_path = get_random_action_audio()

    expected_label = audio_path.parent.name

    expected_state = {
        "bat": "ON",
        "tat": "OFF",
    }[expected_label]

    print(f"Dataset        : {DATASET_DIR}")
    print(f"Audio          : {audio_path}")
    print(f"Expected label : {expected_label}")
    print(f"Expected state : {expected_state}")

    # --------------------------------------------------------
    # Real AI
    # --------------------------------------------------------

    print("\nLoading AI model...")

    ai_service = AIService()

    print(f"AI ready       : {ai_service.ready}")

    if not ai_service.ready:
        print(f"AI error       : {ai_service.load_error}")
        return

    # --------------------------------------------------------
    # Fake dependencies
    # --------------------------------------------------------

    audio_repository = FakeAudioRepository(audio_path)

    mqtt_service = FakeMqttService()

    voice_service = VoiceCommandService(
        ai_service=ai_service,
        audio_repository=audio_repository,
        mqtt_service=mqtt_service,
    )

    # --------------------------------------------------------
    # Fake recording metadata
    # --------------------------------------------------------

    record = {
        "audio_id": "voice_test_001",
        "recording_id": "voice_test_001",
        "session_id": "voice_test_001",
        "device_id": "esp32_01",

        # Quan trọng:
        # VoiceCommandService chỉ nhận 0.5 -> 1.5 giây
        "duration": 1.0,
    }

    # --------------------------------------------------------
    # Run
    # --------------------------------------------------------

    print("\nRunning VoiceCommandService...")

    result = voice_service.process(record)

    # --------------------------------------------------------
    # Result
    # --------------------------------------------------------

    print("\n" + "=" * 70)
    print("VOICE COMMAND RESULT")
    print("=" * 70)

    print(f"Predicted label : {result.label}")
    print(f"Confidence      : {result.confidence}")
    print(f"Accepted        : {result.accepted}")
    print(f"Command         : {result.command}")
    print(f"State           : {result.state}")
    print(f"Published       : {result.published}")
    print(f"Reason          : {result.reason}")

    # --------------------------------------------------------
    # MQTT captured commands
    # --------------------------------------------------------

    print("\n" + "=" * 70)
    print("MQTT COMMAND")
    print("=" * 70)

    if mqtt_service.commands:

        for command in mqtt_service.commands:
            print(f"Device  : {command['device_id']}")
            print(f"Payload : {command['payload']}")

    else:
        print("No MQTT command was published.")

    # --------------------------------------------------------
    # Validation
    # --------------------------------------------------------

    print("\n" + "=" * 70)
    print("VALIDATION")
    print("=" * 70)

    success = True

    if result.label != expected_label:
        print(
            f"FAIL: Expected label={expected_label}, "
            f"but got {result.label}"
        )
        success = False

    if not result.accepted:
        print("FAIL: AI prediction was rejected")
        success = False

    if result.command != "LIGHT":
        print(
            f"FAIL: Expected command=LIGHT, "
            f"but got {result.command}"
        )
        success = False

    if result.state != expected_state:
        print(
            f"FAIL: Expected state={expected_state}, "
            f"but got {result.state}"
        )
        success = False

    if not result.published:
        print("FAIL: MQTT command was not published")
        success = False

    if result.reason != "PUBLISHED":
        print(
            f"FAIL: Expected reason=PUBLISHED, "
            f"but got {result.reason}"
        )
        success = False

    if len(mqtt_service.commands) != 1:
        print(
            f"FAIL: Expected exactly 1 MQTT command, "
            f"got {len(mqtt_service.commands)}"
        )
        success = False

    if success:
        print("PASS: Full VoiceCommandService inference flow works.")


if __name__ == "__main__":
    main()