#include "wifi_manager.h"
#include "config.h"
#include "mqtt_manager.h"
#include "audio_player.h"
#include "microphone_recorder.h"

#include <ArduinoJson.h>

namespace {
WifiManager wifiManager;
MqttManager mqttManager;
AudioPlayer audioPlayer;
MicrophoneRecorder microphoneRecorder;
bool lastWifiState = false;
bool lastMqttState = false;

void publishState(const char* requestId, const char* status, const char* audioId = nullptr) {
  char payload[192];
  if (audioId != nullptr) {
    snprintf(payload, sizeof(payload),
             "{\"device_id\":\"%s\",\"request_id\":\"%s\",\"audio_id\":\"%s\",\"status\":\"%s\"}",
             DEVICE_ID, requestId, audioId, status);
  } else {
    snprintf(payload, sizeof(payload),
             "{\"device_id\":\"%s\",\"request_id\":\"%s\",\"status\":\"%s\"}",
             DEVICE_ID, requestId, status);
  }
  mqttManager.publishStatus(payload);
}

void publishRecordingState(const char* requestId, const char* status,
                           const char* recordingId) {
  char payload[224];
  snprintf(payload, sizeof(payload),
           "{\"device_id\":\"%s\",\"request_id\":\"%s\","
           "\"recording_id\":\"%s\",\"status\":\"%s\"}",
           DEVICE_ID, requestId == nullptr ? "" : requestId,
           recordingId == nullptr ? "" : recordingId, status);
  mqttManager.publishStatus(payload);
}

void publishError(const char* requestId, const char* code, const char* message) {
  char payload[240];
  snprintf(payload, sizeof(payload),
           "{\"device_id\":\"%s\",\"request_id\":\"%s\",\"error_code\":\"%s\",\"message\":\"%s\"}",
           DEVICE_ID, requestId == nullptr ? "" : requestId, code, message);
  mqttManager.publishError(payload);
}

void publishEvent(const char* requestId, const char* event, const char* audioId = nullptr) {
  char payload[192];
  snprintf(payload, sizeof(payload),
           "{\"device_id\":\"%s\",\"request_id\":\"%s\",\"audio_id\":\"%s\",\"event\":\"%s\"}",
           DEVICE_ID, requestId == nullptr ? "" : requestId,
           audioId == nullptr ? "" : audioId, event);
  mqttManager.publishEvent(payload);
}

void publishRecordingEvent(const char* requestId, const char* event,
                           const char* recordingId) {
  char payload[224];
  snprintf(payload, sizeof(payload),
           "{\"device_id\":\"%s\",\"request_id\":\"%s\","
           "\"recording_id\":\"%s\",\"event\":\"%s\"}",
           DEVICE_ID, requestId == nullptr ? "" : requestId,
           recordingId == nullptr ? "" : recordingId, event);
  mqttManager.publishEvent(payload);
}

void onMqttCommand(const char* payload, size_t length) {
  JsonDocument command;
  const DeserializationError parseError = deserializeJson(command, payload, length);
  const char* requestId = command["request_id"] | "";
  const char* action = command["command"] | "";
  if (parseError) {
    publishError("", "INVALID_JSON", "Command is not valid JSON");
    return;
  }
  if (requestId[0] == '\0' || action[0] == '\0') {
    publishError(requestId, "COMMAND_FIELDS_MISSING", "request_id and command are required");
    return;
  }

  if (strcmp(action, "START_RECORDING") == 0) {
    const char* recordingId = command["recording_id"] | "";
    const uint32_t duration = command["duration_seconds"] | RECORDING_DEFAULT_SECONDS;
    if (recordingId[0] == '\0' || duration == 0 || duration > RECORDING_MAX_SECONDS) {
      publishError(requestId, "RECORDING_FIELDS_INVALID",
                   "recording_id and duration_seconds are required");
      return;
    }
    if (audioPlayer.isActive()) {
      const char* interruptedAudioId = audioPlayer.audioId();
      audioPlayer.stop();
      publishEvent(requestId, "PLAYBACK_INTERRUPTED", interruptedAudioId);
    }
    if (!microphoneRecorder.start(requestId, recordingId, duration)) {
      publishError(requestId, "MICROPHONE_START_FAILED",
                   "Unable to initialize INMP441 recording");
      return;
    }
    publishRecordingState(requestId, "RECORDING", recordingId);
    return;
  }

  if (strcmp(action, "STOP_RECORDING") == 0) {
    if (!microphoneRecorder.stop()) {
      publishError(requestId, "INVALID_STATE",
                   "STOP_RECORDING requires an active recording session");
    }
    return;
  }

  if (strcmp(action, "STOP") == 0) {
    const bool recordingStopped = !microphoneRecorder.isRecording() || microphoneRecorder.stop();
    audioPlayer.stop();
    if (!recordingStopped) {
      publishError(requestId, "MICROPHONE_STOP_FAILED",
                   "Unable to finish the active recording");
      return;
    }
    publishState(requestId, "STOPPED");
    return;
  }

  if (strcmp(action, "PAUSE") == 0) {
    if (!audioPlayer.pause()) {
      publishError(requestId, "INVALID_STATE", "PAUSE requires an active playback session");
      return;
    }
    publishState(requestId, "PAUSED", audioPlayer.audioId());
    return;
  }

  if (strcmp(action, "SET_VOLUME") == 0) {
    const int volume = command["volume"] | -1;
    if (volume < 0 || volume > 100 || !audioPlayer.setVolume(static_cast<uint8_t>(volume))) {
      publishError(requestId, "VOLUME_INVALID", "volume must be an integer from 0 to 100");
      return;
    }
    publishEvent(requestId, "VOLUME_CHANGED");
    return;
  }

  if (strcmp(action, "PLAY") == 0) {
    const char* audioId = command["audio_id"] | "";
    const char* audioUrl = command["audio_url"] | "";
    if (audioId[0] == '\0' || audioUrl[0] == '\0') {
      publishError(requestId, "PLAY_FIELDS_MISSING", "audio_id and audio_url are required");
      return;
    }
    if (microphoneRecorder.isRecording() && !microphoneRecorder.stop()) {
      publishError(requestId, "MICROPHONE_STOP_FAILED",
                   "Unable to finish the active recording before playback");
      return;
    }
    publishState(requestId, "BUFFERING", audioId);
    if (!audioPlayer.play(requestId, audioId, audioUrl)) {
      publishState(requestId, "ERROR", audioId);
      publishError(requestId, "AUDIO_DOWNLOAD_FAILED", "Unable to open audio stream");
      audioPlayer.takeFailed();
      return;
    }
    publishState(requestId, "PLAYING", audioId);
    return;
  }

  publishError(requestId, "UNKNOWN_COMMAND", "Unsupported command");
}
}  // namespace

void setup() {
  Serial.begin(115200);
  delay(100);
  Serial.println("ESP32 audio firmware");
  wifiManager.begin(WIFI_SSID, WIFI_PASSWORD);
  mqttManager.begin(MQTT_HOST, MQTT_PORT, DEVICE_ID, MQTT_USERNAME,
                    MQTT_PASSWORD, onMqttCommand);
  microphoneRecorder.begin(&mqttManager);
}

void loop() {
  wifiManager.update();
  if (wifiManager.isConnected()) {
    mqttManager.update();
    audioPlayer.update();
    microphoneRecorder.update();
  }

  const bool connected = wifiManager.isConnected();
  if (connected != lastWifiState) {
    lastWifiState = connected;
    Serial.println(connected ? "WiFi: connected" : "WiFi: disconnected");
  }

  const bool mqttConnected = mqttManager.isConnected();
  if (mqttConnected != lastMqttState) {
    lastMqttState = mqttConnected;
    Serial.println(mqttConnected ? "MQTT: connected" : "MQTT: disconnected");
  }

  if (audioPlayer.takeCompleted()) {
    publishState(audioPlayer.requestId(), "STOPPED", audioPlayer.audioId());
    publishEvent(audioPlayer.requestId(), "PLAY_COMPLETED", audioPlayer.audioId());
  }

  if (audioPlayer.takeFailed()) {
    publishState(audioPlayer.requestId(), "ERROR", audioPlayer.audioId());
    publishError(audioPlayer.requestId(), "AUDIO_PLAYBACK_FAILED", "Audio playback stopped after a stream or decoder failure");
  }

  if (microphoneRecorder.takeCompleted()) {
    publishRecordingState(microphoneRecorder.requestId(), "STOPPED",
                          microphoneRecorder.recordingId());
    publishRecordingEvent(microphoneRecorder.requestId(), "RECORDING_COMPLETED",
                          microphoneRecorder.recordingId());
  }

  if (microphoneRecorder.takeFailed()) {
    publishRecordingState(microphoneRecorder.requestId(), "ERROR",
                          microphoneRecorder.recordingId());
    publishError(microphoneRecorder.requestId(), "MICROPHONE_RECORDING_FAILED",
                 "Audio chunk publishing or INMP441 capture failed");
  }

}
