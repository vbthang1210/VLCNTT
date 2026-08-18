#include "microphone_streamer.h"

#include <stdio.h>

#include "config.h"

MicrophoneStreamer::MicrophoneStreamer() = default;

bool MicrophoneStreamer::begin() {
  // The speaker path already uses the other I2S controller through
  // AudioOutputI2S. Keep the microphone on I2S1 so capture and playback
  // do not compete for the same controller.
  if (!i2s_.setPort(I2S_NUM_1)) {
    Serial.println("[MIC] Failed to select I2S1");
    return false;
  }

  i2s_.setPins(
      MIC_I2S_BCLK_PIN,
      MIC_I2S_WS_PIN,
      -1,
      MIC_I2S_DIN_PIN);

  // INMP441 outputs a 24-bit I2S word inside a 32-bit slot. The development
  // wiring assumes L/R is tied to GND, therefore the left slot is selected.
  ready_ = i2s_.begin(
      I2S_MODE_STD,
      MIC_SAMPLE_RATE,
      I2S_DATA_BIT_WIDTH_32BIT,
      I2S_SLOT_MODE_MONO,
      I2S_STD_SLOT_LEFT,
      I2S_ROLE_MASTER);

  if (!ready_) {
    Serial.println("[MIC] I2S initialization failed");
    return false;
  }

  Serial.print("[MIC] Ready | BCLK=");
  Serial.print(MIC_I2S_BCLK_PIN);
  Serial.print(" WS=");
  Serial.print(MIC_I2S_WS_PIN);
  Serial.print(" DIN=");
  Serial.print(MIC_I2S_DIN_PIN);
  Serial.print(" rate=");
  Serial.println(MIC_SAMPLE_RATE);

  nextCaptureAt_ = millis() + 200;
  return true;
}

bool MicrophoneStreamer::isReady() const {
  return ready_;
}

void MicrophoneStreamer::update(MqttManager& mqtt, bool allowCapture) {
  if (!ready_ || !allowCapture || !mqtt.isConnected()) {
    return;
  }

  const uint32_t now = millis();
  if (static_cast<int32_t>(now - nextCaptureAt_) < 0) {
    return;
  }

  captureWindow(mqtt);
  nextCaptureAt_ = millis() + MIC_WINDOW_GAP_MS;
}

bool MicrophoneStreamer::captureWindow(MqttManager& mqtt) {
  static int32_t rawSamples[MIC_READ_SAMPLES];
  static int16_t pcmSamples[MIC_READ_SAMPLES];

  const size_t targetSamples =
      static_cast<size_t>(MIC_SAMPLE_RATE) * MIC_CAPTURE_MS / 1000UL;

  if (targetSamples == 0) {
    return false;
  }

  // Read one chunk before opening the MQTT session. This prevents creating
  // an empty backend session when the microphone/I2S input has no data.
  const size_t firstBytes = i2s_.readBytes(
      reinterpret_cast<char*>(rawSamples),
      sizeof(rawSamples));

  const size_t firstSamples = firstBytes / sizeof(int32_t);
  if (firstSamples == 0) {
    Serial.println("[MIC] No I2S samples received");
    return false;
  }

  char sessionId[64];
  snprintf(
      sessionId,
      sizeof(sessionId),
      "mic_%lu_%lu",
      static_cast<unsigned long>(millis()),
      static_cast<unsigned long>(sessionCounter_++));

  char startPayload[256];
  snprintf(
      startPayload,
      sizeof(startPayload),
      "{\"device_id\":\"%s\",\"session_id\":\"%s\",\"sample_rate\":%d,\"channels\":1,\"sample_width\":2,\"encoding\":\"pcm_s16le\"}",
      DEVICE_ID,
      sessionId,
      MIC_SAMPLE_RATE);

  if (!mqtt.publishAudioStart(startPayload)) {
    Serial.println("[MIC] Failed to publish audio/start");
    return false;
  }

  size_t sentSamples = 0;

  const size_t firstToSend =
      firstSamples > targetSamples ? targetSamples : firstSamples;
  convertToPcm16(rawSamples, pcmSamples, firstToSend);

  if (!mqtt.publishAudioData(
          reinterpret_cast<const uint8_t*>(pcmSamples),
          firstToSend * sizeof(int16_t))) {
    Serial.println("[MIC] Failed to publish first audio/data chunk");
    return false;
  }

  sentSamples += firstToSend;
  mqtt.update();

  while (sentSamples < targetSamples && mqtt.isConnected()) {
    const size_t remaining = targetSamples - sentSamples;
    const size_t requestedSamples =
        remaining < MIC_READ_SAMPLES ? remaining : MIC_READ_SAMPLES;

    const size_t bytesRead = i2s_.readBytes(
        reinterpret_cast<char*>(rawSamples),
        requestedSamples * sizeof(int32_t));

    const size_t samplesRead = bytesRead / sizeof(int32_t);
    if (samplesRead == 0) {
      Serial.println("[MIC] I2S read stopped before window completed");
      break;
    }

    convertToPcm16(rawSamples, pcmSamples, samplesRead);

    if (!mqtt.publishAudioData(
            reinterpret_cast<const uint8_t*>(pcmSamples),
            samplesRead * sizeof(int16_t))) {
      Serial.println("[MIC] Failed to publish audio/data");
      break;
    }

    sentSamples += samplesRead;
    mqtt.update();
  }

  char endPayload[160];
  snprintf(
      endPayload,
      sizeof(endPayload),
      "{\"device_id\":\"%s\",\"session_id\":\"%s\"}",
      DEVICE_ID,
      sessionId);

  const bool endPublished = mqtt.publishAudioEnd(endPayload);

  Serial.print("[MIC] Window sent | session=");
  Serial.print(sessionId);
  Serial.print(" samples=");
  Serial.print(sentSamples);
  Serial.print("/");
  Serial.println(targetSamples);

  return endPublished && sentSamples == targetSamples;
}

void MicrophoneStreamer::convertToPcm16(
    const int32_t* input,
    int16_t* output,
    size_t samples) {
  for (size_t index = 0; index < samples; ++index) {
    // INMP441 provides a signed 24-bit sample in a 32-bit I2S word.
    // Keeping the upper 16 bits gives signed PCM16 for the backend/model.
    output[index] = static_cast<int16_t>(input[index] >> 16);
  }
}
