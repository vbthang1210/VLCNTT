#include "microphone_recorder.h"

#include <driver/i2s_std.h>
#include <string.h>

#include "mqtt_manager.h"

namespace {
constexpr i2s_port_t kMicrophonePort = I2S_NUM_1;

int16_t toPcm16(int32_t sample) {
  int32_t value = sample >> 14;
  if (value > 32767) {
    value = 32767;
  }
  if (value < -32768) {
    value = -32768;
  }
  return static_cast<int16_t>(value);
}
}  // namespace

void MicrophoneRecorder::begin(MqttManager* mqtt) {
  mqtt_ = mqtt;
}

bool MicrophoneRecorder::start(const char* requestId, const char* recordingId,
                               uint32_t durationSeconds) {
  if (active_ || mqtt_ == nullptr || !mqtt_->isConnected() || requestId == nullptr ||
      recordingId == nullptr || requestId[0] == '\0' || recordingId[0] == '\0') {
    return false;
  }
  if (durationSeconds == 0) {
    durationSeconds = RECORDING_DEFAULT_SECONDS;
  }
  if (durationSeconds > RECORDING_MAX_SECONDS || !installDriver()) {
    return false;
  }
  snprintf(requestId_, sizeof(requestId_), "%s", requestId);
  snprintf(recordingId_, sizeof(recordingId_), "%s", recordingId);
  if (!mqtt_->publishAudioStart(recordingId_, MIC_SAMPLE_RATE, 1, 16)) {
    releaseDriver();
    return false;
  }
  startedAt_ = millis();
  durationMillis_ = durationSeconds * 1000UL;
  Serial.print("RECORDING: started duration_ms=");
  Serial.println(static_cast<unsigned long>(durationMillis_));
  sequence_ = 0;
  sampleCount_ = 0;
  pausedMillis_ = 0;
  disconnectedAt_ = 0;
  networkPaused_ = false;
  pendingChunk_ = false;
  pendingSampleCount_ = 0;
  completed_ = false;
  failed_ = false;
  active_ = true;
  return true;
}

void MicrophoneRecorder::update() {
  if (!active_) {
    return;
  }
  const uint32_t now = millis();
  if (mqtt_ == nullptr || !mqtt_->isConnected()) {
    if (!networkPaused_) {
      networkPaused_ = true;
      disconnectedAt_ = now;
      Serial.println("RECORDING: MQTT disconnected, waiting for recovery");
    }
    if (static_cast<uint32_t>(now - disconnectedAt_) >= MIC_MQTT_RECOVERY_TIMEOUT_MS) {
      Serial.println("RECORDING: MQTT recovery timeout");
      fail();
    }
    return;
  }

  if (networkPaused_) {
    pausedMillis_ += static_cast<uint32_t>(now - disconnectedAt_);
    networkPaused_ = false;
    Serial.println("RECORDING: MQTT recovered");
  }

  if (pendingChunk_) {
    if (!flushPendingChunk()) {
      return;
    }
  } else {
    size_t bytesRead = 0;
    const esp_err_t result = i2s_channel_read(
        rxChannel_, rawSamples_, sizeof(rawSamples_), &bytesRead, 50);
    if (result != ESP_OK) {
      Serial.print("RECORDING: I2S read failed error=");
      Serial.println(static_cast<int>(result));
      fail();
      return;
    }
    const size_t samplesRead = bytesRead / sizeof(int32_t);
    if (samplesRead == 0) {
      return;
    }
    for (size_t index = 0; index < samplesRead; ++index) {
      pcmSamples_[index] = toPcm16(rawSamples_[index]);
    }
    pendingSampleCount_ = samplesRead;
    pendingChunk_ = true;
    if (!flushPendingChunk()) {
      return;
    }
  }

  const uint32_t elapsedMillis = static_cast<uint32_t>(millis() - startedAt_);
  if (elapsedMillis >= pausedMillis_ && elapsedMillis - pausedMillis_ >= durationMillis_) {
    stop();
  }
}

bool MicrophoneRecorder::flushPendingChunk() {
  if (!pendingChunk_) {
    return true;
  }
  if (mqtt_ == nullptr || !mqtt_->isConnected() ||
      !mqtt_->publishAudioChunk(recordingId_, sequence_, pcmSamples_, pendingSampleCount_)) {
    Serial.println("RECORDING: MQTT chunk publish failed; keeping chunk for retry");
    if (mqtt_ == nullptr || !mqtt_->isConnected()) {
      networkPaused_ = true;
      disconnectedAt_ = millis();
    }
    return false;
  }
  ++sequence_;
  sampleCount_ += static_cast<uint32_t>(pendingSampleCount_);
  pendingChunk_ = false;
  pendingSampleCount_ = 0;
  return true;
}

bool MicrophoneRecorder::stop(const char* requestId) {
  if (!active_) {
    return false;
  }
  if (requestId != nullptr && requestId[0] != '\0') {
    snprintf(requestId_, sizeof(requestId_), "%s", requestId);
  }
  if (!flushPendingChunk()) {
    releaseDriver();
    active_ = false;
    failed_ = true;
    return false;
  }
  Serial.print("RECORDING: stopping chunks=");
  Serial.print(static_cast<unsigned long>(sequence_));
  Serial.print(" samples=");
  Serial.println(static_cast<unsigned long>(sampleCount_));
  const bool ended = mqtt_ != nullptr && mqtt_->isConnected() &&
                     mqtt_->publishAudioEnd(recordingId_, sequence_, sampleCount_);
  releaseDriver();
  active_ = false;
  if (ended) {
    completed_ = true;
  } else {
    failed_ = true;
  }
  return ended;
}

bool MicrophoneRecorder::isRecording() const {
  return active_;
}

const char* MicrophoneRecorder::requestId() const {
  return requestId_;
}

const char* MicrophoneRecorder::recordingId() const {
  return recordingId_;
}

bool MicrophoneRecorder::takeCompleted() {
  const bool value = completed_;
  completed_ = false;
  return value;
}

bool MicrophoneRecorder::takeFailed() {
  const bool value = failed_;
  failed_ = false;
  return value;
}

bool MicrophoneRecorder::installDriver() {
  i2s_chan_config_t channelConfig = I2S_CHANNEL_DEFAULT_CONFIG(kMicrophonePort, I2S_ROLE_MASTER);
  channelConfig.dma_desc_num = 8;
  channelConfig.dma_frame_num = MIC_SAMPLES_PER_CHUNK;
  if (i2s_new_channel(&channelConfig, nullptr, &rxChannel_) != ESP_OK) {
    return false;
  }

  i2s_std_config_t config = {};
  config.clk_cfg = I2S_STD_CLK_DEFAULT_CONFIG(MIC_SAMPLE_RATE);
  config.slot_cfg = I2S_STD_PHILIPS_SLOT_DEFAULT_CONFIG(
      I2S_DATA_BIT_WIDTH_32BIT, I2S_SLOT_MODE_MONO);
  config.gpio_cfg.mclk = I2S_GPIO_UNUSED;
  config.gpio_cfg.bclk = static_cast<gpio_num_t>(MIC_I2S_BCLK_PIN);
  config.gpio_cfg.ws = static_cast<gpio_num_t>(MIC_I2S_WS_PIN);
  config.gpio_cfg.dout = I2S_GPIO_UNUSED;
  config.gpio_cfg.din = static_cast<gpio_num_t>(MIC_I2S_SD_PIN);
  config.gpio_cfg.invert_flags.mclk_inv = false;
  config.gpio_cfg.invert_flags.bclk_inv = false;
  config.gpio_cfg.invert_flags.ws_inv = false;
  if (i2s_channel_init_std_mode(rxChannel_, &config) != ESP_OK) {
    i2s_del_channel(rxChannel_);
    rxChannel_ = nullptr;
    return false;
  }
  if (i2s_channel_enable(rxChannel_) != ESP_OK) {
    i2s_del_channel(rxChannel_);
    rxChannel_ = nullptr;
    return false;
  }
  driverReady_ = true;
  return true;
}

void MicrophoneRecorder::releaseDriver() {
  if (rxChannel_ != nullptr) {
    if (driverReady_) {
      i2s_channel_disable(rxChannel_);
    }
    i2s_del_channel(rxChannel_);
    rxChannel_ = nullptr;
    driverReady_ = false;
  }
}

void MicrophoneRecorder::fail() {
  Serial.println("RECORDING: failed");
  releaseDriver();
  active_ = false;
  pendingChunk_ = false;
  pendingSampleCount_ = 0;
  networkPaused_ = false;
  failed_ = true;
}
