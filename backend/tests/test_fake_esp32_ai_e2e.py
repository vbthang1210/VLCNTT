from __future__ import annotations

import json
import random
import secrets
import socket
import time
import wave
from pathlib import Path
from threading import Event

import paho.mqtt.client as mqtt

from app import create_app


# ============================================================
# Paths
# ============================================================

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_DIR.parent
DATASET_DIR = PROJECT_ROOT / "dataset" / "processed"


# ============================================================
# MQTT config
# ============================================================

MQTT_HOST = "127.0.0.1"
MQTT_PORT = 1883


def broker_available() -> bool:
    with socket.socket() as sock:
        sock.settimeout(1)

        try:
            sock.connect((MQTT_HOST, MQTT_PORT))
            return True
        except OSError:
            return False


# ============================================================
# Pick random BAT/TAT WAV
# ============================================================

def get_random_action_audio() -> Path:
    files = []

    for label in ["bat", "tat"]:
        files.extend((DATASET_DIR / label).rglob("*.wav"))

    files = list(files)

    if not files:
        raise RuntimeError("No bat/tat WAV files found")

    return random.choice(files)


# ============================================================
# Read WAV as raw PCM16
# ============================================================

def read_pcm16_wav(path: Path) -> bytes:
    with wave.open(str(path), "rb") as wav_file:

        sample_rate = wav_file.getframerate()
        channels = wav_file.getnchannels()
        sample_width = wav_file.getsampwidth()

        if sample_rate != 16000:
            raise RuntimeError(
                f"Expected 16000 Hz, got {sample_rate}"
            )

        if channels != 1:
            raise RuntimeError(
                f"Expected mono, got {channels} channels"
            )

        if sample_width != 2:
            raise RuntimeError(
                f"Expected PCM16, got {sample_width * 8}-bit"
            )

        return wav_file.readframes(wav_file.getnframes())


# ============================================================
# Main E2E test
# ============================================================

def main():

    print("=" * 70)
    print("FAKE ESP32 -> MQTT -> BACKEND -> AI -> MQTT E2E TEST")
    print("=" * 70)

    # --------------------------------------------------------
    # Check Mosquitto
    # --------------------------------------------------------

    if not broker_available():
        print("ERROR: Mosquitto is not running on 127.0.0.1:1883")
        print()
        print("Start it first:")
        print("  brew services start mosquitto")
        return

    # --------------------------------------------------------
    # Random audio
    # --------------------------------------------------------

    audio_path = get_random_action_audio()

    expected_label = audio_path.parent.name

    expected_state = {
        "bat": "ON",
        "tat": "OFF",
    }[expected_label]

    pcm_data = read_pcm16_wav(audio_path)

    sample_count = len(pcm_data) // 2

    print(f"Audio          : {audio_path}")
    print(f"Expected label : {expected_label}")
    print(f"Expected state : {expected_state}")
    print(f"PCM bytes      : {len(pcm_data)}")
    print(f"Samples        : {sample_count}")
    print(f"Duration       : {sample_count / 16000:.4f}s")

    # --------------------------------------------------------
    # IDs
    # --------------------------------------------------------

    suffix = secrets.token_hex(3)

    device_id = f"esp32_test_{suffix}"
    recording_id = f"rec_{suffix}"

    # --------------------------------------------------------
    # Backend app
    # --------------------------------------------------------

    test_storage = BACKEND_DIR / "storage" / "e2e_test_audio"
    test_metadata = BACKEND_DIR / "storage" / "e2e_test_metadata.json"

    app = create_app(
        {
            "TESTING": "true",

            "MQTT_ENABLED": "true",
            "MQTT_HOST": MQTT_HOST,
            "MQTT_PORT": str(MQTT_PORT),

            "AUDIO_STORAGE_PATH": str(test_storage),
            "METADATA_PATH": str(test_metadata),

            "RECORDING_DEFAULT_SECONDS": "1",
            "RECORDING_MAX_SECONDS": "60",
        }
    )

    mqtt_service = app.extensions["mqtt_service"]
    ai_service = app.extensions["ai_service"]

    print()
    print(f"AI ready       : {ai_service.ready}")

    if not ai_service.ready:
        print(f"AI load error  : {ai_service.load_error}")
        return

    # --------------------------------------------------------
    # Subscribe to command sent back to ESP32
    # --------------------------------------------------------

    command_event = Event()
    received_commands = []

    listener = mqtt.Client(
        client_id=f"fake-esp32-listener-{suffix}"
    )

    def on_command(_client, _userdata, message):

        payload = json.loads(
            message.payload.decode("utf-8")
        )

        received_commands.append(
            {
                "topic": message.topic,
                "payload": payload,
            }
        )

        command_event.set()

    listener.on_message = on_command

    # --------------------------------------------------------
    # Fake ESP32 publisher
    # --------------------------------------------------------

    publisher = mqtt.Client(
        client_id=f"fake-esp32-publisher-{suffix}"
    )

    try:

        # ----------------------------------------------------
        # Start backend MQTT
        # ----------------------------------------------------

        print("\nStarting Backend MQTT...")

        mqtt_service.start()

        deadline = time.time() + 5

        while (
            not mqtt_service.is_connected()
            and time.time() < deadline
        ):
            time.sleep(0.05)

        if not mqtt_service.is_connected():
            print("ERROR: Backend cannot connect to Mosquitto")
            return

        print("Backend MQTT connected.")

        # ----------------------------------------------------
        # Start listener
        # ----------------------------------------------------

        listener.connect(
            MQTT_HOST,
            MQTT_PORT,
            5,
        )

        listener.subscribe(
            f"esp32/{device_id}/command",
            qos=1,
        )

        listener.loop_start()

        # ----------------------------------------------------
        # Start fake ESP32 publisher
        # ----------------------------------------------------

        publisher.connect(
            MQTT_HOST,
            MQTT_PORT,
            5,
        )

        publisher.loop_start()

        # ----------------------------------------------------
        # AUDIO START
        # ----------------------------------------------------

        start_payload = {
            "device_id": device_id,
            "recording_id": recording_id,
            "sample_rate": 16000,
            "channels": 1,
            "bits_per_sample": 16,
            "duration_seconds": 1,
        }

        print("\nSending audio/start...")

        publisher.publish(
            f"esp32/{device_id}/audio/start",
            json.dumps(start_payload),
            qos=1,
        ).wait_for_publish(timeout=3)

        # ----------------------------------------------------
        # AUDIO CHUNKS
        # ----------------------------------------------------

        #
        # ESP32 config hiện tại dùng 512 samples/chunk.
        #
        # PCM16:
        #     512 samples * 2 bytes = 1024 bytes/chunk
        #

        chunk_size = 512 * 2

        chunks = [
            pcm_data[i:i + chunk_size]
            for i in range(0, len(pcm_data), chunk_size)
        ]

        print(
            f"Sending {len(chunks)} PCM chunks..."
        )

        for sequence, chunk in enumerate(chunks):

            topic = (
                f"esp32/{device_id}/audio/chunk/"
                f"{recording_id}/{sequence}"
            )

            publisher.publish(
                topic,
                chunk,
                qos=1,
            ).wait_for_publish(timeout=3)

        # ----------------------------------------------------
        # AUDIO END
        # ----------------------------------------------------

        end_payload = {
            "device_id": device_id,
            "recording_id": recording_id,
            "total_chunks": len(chunks),
            "sample_count": sample_count,
        }

        print("Sending audio/end...")

        publisher.publish(
            f"esp32/{device_id}/audio/end",
            json.dumps(end_payload),
            qos=1,
        ).wait_for_publish(timeout=3)

        # ----------------------------------------------------
        # Wait AI -> MQTT command
        # ----------------------------------------------------

        print("\nWaiting for AI command...")

        received = command_event.wait(timeout=10)

        print("\n" + "=" * 70)
        print("RESULT")
        print("=" * 70)

        if not received:
            print("FAIL: No MQTT command received from Backend")
            return

        command = received_commands[0]

        print(f"Topic   : {command['topic']}")
        print(f"Payload : {command['payload']}")

        payload = command["payload"]

        # ----------------------------------------------------
        # Validate
        # ----------------------------------------------------

        success = True

        if payload.get("command") != "LIGHT":
            print(
                f"FAIL: expected command LIGHT, "
                f"got {payload.get('command')}"
            )
            success = False

        if payload.get("state") != expected_state:
            print(
                f"FAIL: expected state {expected_state}, "
                f"got {payload.get('state')}"
            )
            success = False

        if success:
            print()
            print(
                "PASS: Fake ESP32 -> MQTT -> WAV -> AI "
                "-> MQTT LIGHT command works."
            )

    finally:

        publisher.loop_stop()
        publisher.disconnect()

        listener.loop_stop()
        listener.disconnect()

        mqtt_service.stop()


if __name__ == "__main__":
    main()