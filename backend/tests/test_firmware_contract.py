from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MQTT_MANAGER = (ROOT / "main" / "mqtt_manager.cpp").read_text(encoding="utf-8")
MAIN = (ROOT / "main" / "main.ino").read_text(encoding="utf-8")
MICROPHONE = (ROOT / "main" / "microphone_recorder.cpp").read_text(encoding="utf-8")
MICROPHONE_HEADER = (ROOT / "main" / "microphone_recorder.h").read_text(encoding="utf-8")


def section(source: str, start: str, end: str) -> str:
    start_index = source.index(start)
    end_index = source.index(end, start_index)
    return source[start_index:end_index]


def test_oversized_command_error_uses_runtime_device_id():
    block = section(MQTT_MANAGER, "if (messageSize < 0", "static char payload")
    assert "deviceId_" in block
    assert '"esp32_01"' not in block


def test_set_volume_does_not_publish_idle_status():
    block = section(MAIN, 'if (strcmp(action, "SET_VOLUME") == 0)', 'if (strcmp(action, "PLAY") == 0)')
    assert 'publishState(requestId, "IDLE")' not in block
    assert 'publishEvent(requestId, "VOLUME_CHANGED")' in block


def test_start_recording_stops_active_playback_first():
    block = section(MAIN, 'if (strcmp(action, "START_RECORDING") == 0)', 'if (strcmp(action, "STOP_RECORDING") == 0)')
    assert "audioPlayer.isActive()" in block
    assert block.index("audioPlayer.stop()") < block.index("microphoneRecorder.start")


def test_play_stops_active_recording_first():
    block = section(MAIN, 'if (strcmp(action, "PLAY") == 0)', 'publishError(requestId, "UNKNOWN_COMMAND"')
    assert "microphoneRecorder.isRecording()" in block
    assert block.index("microphoneRecorder.stop()") < block.index("audioPlayer.play")


def test_stop_command_stops_playback_and_recording():
    block = section(MAIN, 'if (strcmp(action, "STOP") == 0)', 'if (strcmp(action, "PAUSE") == 0)')
    assert "microphoneRecorder.stop()" in block
    assert "audioPlayer.stop()" in block


def test_loop_does_not_add_fixed_audio_delay():
    assert "delay(10);" not in MAIN


def test_microphone_uses_new_i2s_standard_driver():
    assert "#include <driver/i2s_std.h>" in MICROPHONE
    assert "i2s_driver_install" not in MICROPHONE
    assert "i2s_channel_read" in MICROPHONE


def test_mqtt_connect_failures_are_reported_on_serial():
    assert "client_.connectError()" in MQTT_MANAGER


def test_recording_retries_pending_chunks_during_mqtt_reconnect():
    assert "pendingChunk_" in MICROPHONE_HEADER
    assert "networkPaused_" in MICROPHONE_HEADER
    assert "flushPendingChunk" in MICROPHONE
    assert "MIC_MQTT_RECOVERY_TIMEOUT_MS" in MICROPHONE


def test_audio_chunks_use_nonblocking_mqtt_qos():
    block = section(MQTT_MANAGER, "bool MqttManager::publishAudioChunk", "bool MqttManager::publishAudioEnd")
    assert "false, 0" in block
