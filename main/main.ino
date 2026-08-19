#include "wifi_manager.h"
#include "config.h"
#include "mqtt_manager.h"
#include "audio_player.h"
#include "microphone_recorder.h"
#include "led_manager.h"

#include <ArduinoJson.h>
#include <string.h>

namespace {
WifiManager wifiManager;
MqttManager mqttManager;
AudioPlayer audioPlayer;
MicrophoneRecorder microphoneRecorder;
LedManager ledManager(LED_PIN);
bool lastWifiState = false;
bool lastMqttState = false;

bool isSafeCommandIdentifier(const char* value) {
  if (value == nullptr || value[0] == '\0') {
    return false;
  }
  for (size_t index = 0; value[index] != '\0'; ++index) {
    if (index >= 63) {
      return false;
    }
    const char character = value[index];
    if (!((character >= 'a' && character <= 'z') ||
          (character >= 'A' && character <= 'Z') ||
          (character >= '0' && character <= '9') ||
          character == '_' || character == '-')) {
      return false;
    }
  }
  return true;
}

bool serializePayload(JsonDocument& document, char* payload, size_t capacity) {
  const size_t required = measureJson(document);
  const size_t written = serializeJson(document, payload, capacity);
  return required + 1 <= capacity && written < capacity && written == required;
}

void publishPayloadTooLargeError() {
  JsonDocument error;
  error["device_id"] = DEVICE_ID;
  error["request_id"] = "";
  error["error_code"] = "PAYLOAD_TOO_LARGE";
  error["message"] = "Outgoing MQTT payload exceeds buffer";

  char payload[160];
  if (serializePayload(error, payload, sizeof(payload))) {
    mqttManager.publishError(payload);
  }
}

void publishState(const char* requestId, const char* status, const char* audioId = nullptr) {
  JsonDocument state;
  state["device_id"] = DEVICE_ID;
  state["request_id"] = requestId == nullptr ? "" : requestId;
  if (audioId != nullptr) {
    state["audio_id"] = audioId;
  }
  state["status"] = status == nullptr ? "" : status;

  char payload[192];
  if (!serializePayload(state, payload, sizeof(payload))) {
    publishPayloadTooLargeError();
    return;
  }
  mqttManager.publishStatus(payload);
}

void publishRecordingState(const char* requestId, const char* status,
                           const char* recordingId) {
  JsonDocument state;
  state["device_id"] = DEVICE_ID;
  state["request_id"] = requestId == nullptr ? "" : requestId;
  state["recording_id"] = recordingId == nullptr ? "" : recordingId;
  state["status"] = status == nullptr ? "" : status;

  char payload[224];
  if (!serializePayload(state, payload, sizeof(payload))) {
    publishPayloadTooLargeError();
    return;
  }
  mqttManager.publishStatus(payload);
}

void publishError(const char* requestId, const char* code, const char* message) {
  JsonDocument error;
  error["device_id"] = DEVICE_ID;
  error["request_id"] = requestId == nullptr ? "" : requestId;
  error["error_code"] = code == nullptr ? "" : code;
  error["message"] = message == nullptr ? "" : message;

  char payload[240];
  if (!serializePayload(error, payload, sizeof(payload))) {
    publishPayloadTooLargeError();
    return;
  }
  mqttManager.publishError(payload);
}

void publishEvent(const char* requestId, const char* event, const char* audioId = nullptr) {
  JsonDocument eventDocument;
  eventDocument["device_id"] = DEVICE_ID;
  eventDocument["request_id"] = requestId == nullptr ? "" : requestId;
  if (audioId != nullptr) {
    eventDocument["audio_id"] = audioId;
  }
  eventDocument["event"] = event == nullptr ? "" : event;

  char payload[192];
  if (!serializePayload(eventDocument, payload, sizeof(payload))) {
    publishPayloadTooLargeError();
    return;
  }
  mqttManager.publishEvent(payload);
}

void publishRecordingEvent(const char* requestId, const char* event,
                           const char* recordingId) {
  JsonDocument eventDocument;
  eventDocument["device_id"] = DEVICE_ID;
  eventDocument["request_id"] = requestId == nullptr ? "" : requestId;
  eventDocument["recording_id"] = recordingId == nullptr ? "" : recordingId;
  eventDocument["event"] = event == nullptr ? "" : event;

  char payload[224];
  if (!serializePayload(eventDocument, payload, sizeof(payload))) {
    publishPayloadTooLargeError();
    return;
  }
  mqttManager.publishEvent(payload);
}

void publishLightChanged(const char* requestId, const char* lightState) {
  JsonDocument event;
  event["device_id"] = DEVICE_ID;
  event["request_id"] = requestId == nullptr ? "" : requestId;
  event["event"] = "LIGHT_CHANGED";
  event["light_state"] = lightState == nullptr ? "" : lightState;

  char payload[192];
  if (!serializePayload(event, payload, sizeof(payload))) {
    publishPayloadTooLargeError();
    return;
  }
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
    publishError("", "COMMAND_FIELDS_MISSING", "request_id and command are required");
    return;
  }
  if (!isSafeCommandIdentifier(requestId)) {
    publishError("", "COMMAND_FIELDS_INVALID", "request_id contains unsafe characters");
    return;
  }

  if (strcmp(action, "START_RECORDING") == 0) {
    const char* recordingId = command["recording_id"] | "";
    const uint32_t duration = command["duration_seconds"] | RECORDING_DEFAULT_SECONDS;
    if (!isSafeCommandIdentifier(recordingId) || duration == 0 || duration > RECORDING_MAX_SECONDS) {
      publishError(requestId, "RECORDING_FIELDS_INVALID",
                   "recording_id and duration_seconds are required");
      return;
    }
    Serial.print("RECORDING: command duration_s=");
    Serial.println(static_cast<unsigned long>(duration));
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
    if (!microphoneRecorder.stop(requestId)) {
      publishError(requestId, "INVALID_STATE",
                   "STOP_RECORDING requires an active recording session");
    }
    return;
  }

  if (strcmp(action, "STOP") == 0) {
    const bool recordingStopped = !microphoneRecorder.isRecording() || microphoneRecorder.stop(requestId);
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

  if (strcmp(action, "RESUME") == 0) {
    if (!audioPlayer.resume()) {
      publishError(requestId, "INVALID_STATE", "RESUME requires a paused playback session");
      return;
    }
    publishState(requestId, "PLAYING", audioPlayer.audioId());
    return;
  }

  if (strcmp(action, "LIGHT") == 0) {
    const char* lightState = command["state"] | "";
    if (strcmp(lightState, "ON") == 0) {
      ledManager.turnOn();
      publishLightChanged(requestId, "ON");
      return;
    }
    if (strcmp(lightState, "OFF") == 0) {
      ledManager.turnOff();
      publishLightChanged(requestId, "OFF");
      return;
    }
    publishError(requestId, "LIGHT_STATE_INVALID", "state must be ON or OFF");
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
    if (!isSafeCommandIdentifier(audioId) || audioUrl[0] == '\0' || strlen(audioUrl) >= 256) {
      publishError(requestId, "PLAY_FIELDS_MISSING", "audio_id and audio_url are required");
      return;
    }
    if (microphoneRecorder.isRecording() && !microphoneRecorder.stop(requestId)) {
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
  ledManager.begin();
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
    publishError(audioPlayer.requestId(), "AUDIO_PLAYBACK_FAILED",
                 "Audio playback stopped after a stream or decoder failure");
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
