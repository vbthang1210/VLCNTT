from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MQTT_MANAGER = (ROOT / "main" / "mqtt_manager.cpp").read_text(encoding="utf-8")
MAIN = (ROOT / "main" / "main.ino").read_text(encoding="utf-8")
MICROPHONE = (ROOT / "main" / "microphone_recorder.cpp").read_text(encoding="utf-8")
MICROPHONE_HEADER = (ROOT / "main" / "microphone_recorder.h").read_text(encoding="utf-8")
CONFIG = (ROOT / "main" / "config.h").read_text(encoding="utf-8")


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


def test_recording_default_duration_is_five_seconds():
    assert "#define RECORDING_DEFAULT_SECONDS 5UL" in CONFIG


def test_play_stops_active_recording_first():
    block = section(MAIN, 'if (strcmp(action, "PLAY") == 0)', 'publishError(requestId, "UNKNOWN_COMMAND"')
    assert "microphoneRecorder.isRecording()" in block
    assert block.index("microphoneRecorder.stop(requestId)") < block.index("audioPlayer.play")


def test_stop_command_stops_playback_and_recording():
    block = section(MAIN, 'if (strcmp(action, "STOP") == 0)', 'if (strcmp(action, "PAUSE") == 0)')
    assert "microphoneRecorder.stop(requestId)" in block
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


def test_audio_chunks_use_qos_one_for_reliable_pcm_delivery():
    block = section(MQTT_MANAGER, "bool MqttManager::publishAudioChunk", "bool MqttManager::publishAudioEnd")
    assert "false, 1" in block


def test_light_command_controls_led_and_publishes_event():
    block = section(MAIN, 'if (strcmp(action, "LIGHT") == 0)', 'publishError(requestId, "UNKNOWN_COMMAND"')
    assert 'command["state"]' in block
    assert "ledManager.turnOn()" in block
    assert "ledManager.turnOff()" in block
    assert "publishLightChanged" in block
    assert "LIGHT_CHANGED" in MAIN
    assert "LED_PIN" in CONFIG


def test_light_event_serialization_is_bounded_and_json_safe():
    block = section(MAIN, "void publishLightChanged", "void onMqttCommand")
    assert "JsonDocument event" in block
    assert "serializePayload(event, payload, sizeof(payload))" in block
    helper = section(MAIN, "bool serializePayload", "void publishPayloadTooLargeError")
    assert "measureJson(document)" in helper
    assert "serializeJson(document, payload, capacity)" in helper
    assert "written < capacity" in helper


def test_all_firmware_json_publishers_use_bounded_serialization():
    publishers = (
        ("publishState", "publishRecordingState"),
        ("publishRecordingState", "publishError"),
        ("publishError", "publishEvent"),
        ("publishEvent", "publishRecordingEvent"),
        ("publishRecordingEvent", "onMqttCommand"),
    )
    for name, end in publishers:
        block = section(MAIN, f"void {name}", f"void {end}")
        assert "serializePayload" in block
        assert "snprintf" not in block


def test_mqtt_manager_json_publishers_use_bounded_serialization():
    assert "serializeMqttJson" in MQTT_MANAGER
    connect_block = section(MQTT_MANAGER, "void MqttManager::connectIfDue", "bool MqttManager::publish")
    start_block = section(MQTT_MANAGER, "bool MqttManager::publishAudioStart", "bool MqttManager::publishAudioChunk")
    end_block = section(MQTT_MANAGER, "bool MqttManager::publishAudioEnd", "void MqttManager::receiveCommand")
    error_block = section(MQTT_MANAGER, "if (messageSize < 0", "static char payload")
    for block in (connect_block, start_block, end_block, error_block):
        assert "serializeMqttJson" in block
        assert "snprintf" not in block


def test_mqtt_manager_rejects_unsafe_identifiers_and_topic_truncation():
    assert "bool isSafeIdentifier" in MQTT_MANAGER
    assert "!isSafeIdentifier(recordingId)" in MQTT_MANAGER
    assert "static_cast<size_t>(written) >= sizeof(topic)" in MQTT_MANAGER


def test_command_ingress_bounds_request_recording_audio_ids_and_url():
    start_block = section(MAIN, 'if (strcmp(action, "START_RECORDING") == 0)', 'if (strcmp(action, "STOP_RECORDING") == 0)')
    play_block = section(MAIN, 'if (strcmp(action, "PLAY") == 0)', 'publishError(requestId, "UNKNOWN_COMMAND"')
    assert "isSafeCommandIdentifier(requestId)" in MAIN
    assert "isSafeCommandIdentifier(recordingId)" in start_block
    assert "isSafeCommandIdentifier(audioId)" in play_block
    assert "strlen(audioUrl) >= 256" in play_block


def test_stop_recording_rebinds_completion_to_stop_request():
    stop_recording_block = section(
        MAIN,
        'if (strcmp(action, "STOP_RECORDING") == 0)',
        'if (strcmp(action, "STOP") == 0)',
    )
    stop_block = section(MAIN, 'if (strcmp(action, "STOP") == 0)', 'if (strcmp(action, "PAUSE") == 0)')
    assert "microphoneRecorder.stop(requestId)" in stop_recording_block
    assert "microphoneRecorder.stop(requestId)" in stop_block


def test_resume_command_continues_paused_audio():
    block = section(MAIN, 'if (strcmp(action, "PAUSE") == 0)', 'if (strcmp(action, "LIGHT") == 0)')
    assert 'strcmp(action, "RESUME")' in MAIN
    assert "audioPlayer.resume()" in MAIN
    assert 'publishState(requestId, "PLAYING"' in MAIN


def test_pause_stops_i2s_and_resume_restarts_it():
    audio_player = (ROOT / "main" / "audio_player.cpp").read_text(encoding="utf-8")
    pause_block = section(audio_player, "bool AudioPlayer::pause()", "bool AudioPlayer::resume()")
    resume_block = section(audio_player, "bool AudioPlayer::resume()", "bool AudioPlayer::setVolume")
    assert "output_->SetGain(0.0f)" in pause_block
    assert "output_->flush()" in pause_block
    assert "output_->stop()" in pause_block
    assert "output_->SetGain(static_cast<float>(volume_) / 100.0f)" in pause_block
    assert "output_->begin()" in resume_block
