#include "microphone_recorder.h"

#include <driver/i2s.h>
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
  sequence_ = 0;
  sampleCount_ = 0;
  completed_ = false;
  failed_ = false;
  active_ = true;
  return true;
}

void MicrophoneRecorder::update() {
  if (!active_) {
    return;
  }
  if (mqtt_ == nullptr || !mqtt_->isConnected()) {
    fail();
    return;
  }
  size_t bytesRead = 0;
  const esp_err_t result = i2s_read(
      kMicrophonePort, rawSamples_, sizeof(rawSamples_), &bytesRead, pdMS_TO_TICKS(50));
  if (result != ESP_OK) {
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
  if (!mqtt_->publishAudioChunk(recordingId_, sequence_, pcmSamples_, samplesRead)) {
    fail();
    return;
  }
  ++sequence_;
  sampleCount_ += static_cast<uint32_t>(samplesRead);
  if (static_cast<uint32_t>(millis() - startedAt_) >= durationMillis_) {
    stop();
  }
}

bool MicrophoneRecorder::stop() {
  if (!active_) {
    return false;
  }
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
  i2s_config_t config = {};
  config.mode = static_cast<i2s_mode_t>(I2S_MODE_MASTER | I2S_MODE_RX);
  config.sample_rate = MIC_SAMPLE_RATE;
  config.bits_per_sample = I2S_BITS_PER_SAMPLE_32BIT;
  config.channel_format = I2S_CHANNEL_FMT_ONLY_LEFT;
  config.communication_format = I2S_COMM_FORMAT_STAND_I2S;
  config.intr_alloc_flags = ESP_INTR_FLAG_LEVEL1;
  config.dma_buf_count = 8;
  config.dma_buf_len = MIC_SAMPLES_PER_CHUNK;
  config.use_apll = false;
  config.tx_desc_auto_clear = false;
  config.fixed_mclk = 0;
  if (i2s_driver_install(kMicrophonePort, &config, 0, nullptr) != ESP_OK) {
    return false;
  }

  i2s_pin_config_t pins = {};
  pins.bck_io_num = MIC_I2S_BCLK_PIN;
  pins.ws_io_num = MIC_I2S_WS_PIN;
  pins.data_out_num = I2S_PIN_NO_CHANGE;
  pins.data_in_num = MIC_I2S_SD_PIN;
  if (i2s_set_pin(kMicrophonePort, &pins) != ESP_OK) {
    i2s_driver_uninstall(kMicrophonePort);
    return false;
  }
  i2s_zero_dma_buffer(kMicrophonePort);
  driverReady_ = true;
  return true;
}

void MicrophoneRecorder::releaseDriver() {
  if (driverReady_) {
    i2s_driver_uninstall(kMicrophonePort);
    driverReady_ = false;
  }
}

void MicrophoneRecorder::fail() {
  releaseDriver();
  active_ = false;
  failed_ = true;
}
