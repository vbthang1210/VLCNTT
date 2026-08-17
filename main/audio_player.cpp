#include "audio_player.h"

#include <string.h>

#include "config.h"
#include "AudioFileSourceBuffer.h"
#include "AudioFileSourceHTTPStream.h"
#include "AudioGeneratorMP3.h"
#include "AudioGeneratorWAV.h"
#include "AudioOutputI2S.h"


bool AudioPlayer::play(const char* requestId, const char* audioId,
                       const char* audioUrl) {
  if (requestId == nullptr || audioId == nullptr || audioUrl == nullptr ||
      requestId[0] == '\0' || audioId[0] == '\0' || audioUrl[0] == '\0') {
    result_ = UpdateResult::FAILED;
    failureReported_ = true;
    return false;
  }

  stop();
  completionReported_ = false;
  failureReported_ = false;
  streamFailure_ = false;
  decoderFailure_ = false;
  snprintf(requestId_, sizeof(requestId_), "%s", requestId);
  snprintf(audioId_, sizeof(audioId_), "%s", audioId);
  snprintf(audioUrl_, sizeof(audioUrl_), "%s", audioUrl);

  source_ = new AudioFileSourceHTTPStream();
  source_->SetReconnect(AUDIO_HTTP_RETRY_COUNT, 250);
  source_->RegisterStatusCB(onSourceStatus, this);
  if (!source_->open(audioUrl_)) {
    releaseResources();
    result_ = UpdateResult::FAILED;
    failureReported_ = true;
    return false;
  }

  buffer_ = new AudioFileSourceBuffer(source_, AUDIO_BUFFER_BYTES);
  output_ = new AudioOutputI2S();
  output_->SetPinout(I2S_BCLK_PIN, I2S_WS_PIN, I2S_DOUT_PIN);
  output_->SetGain(static_cast<float>(volume_) / 100.0f);

  if (isWavUrl()) {
    generator_ = new AudioGeneratorWAV();
  } else {
    generator_ = new AudioGeneratorMP3();
  }
  generator_->RegisterStatusCB(onDecoderStatus, this);
  if (!generator_->begin(buffer_, output_)) {
    releaseResources();
    result_ = UpdateResult::FAILED;
    failureReported_ = true;
    return false;
  }
  active_ = true;
  paused_ = false;
  result_ = UpdateResult::PLAYING;
  return true;
}

void AudioPlayer::update() {
  if (!active_ || paused_ || generator_ == nullptr) {
    return;
  }
  if (!generator_->loop()) {
    generator_->stop();
    releaseResources();
    active_ = false;
    if (streamFailure_ || decoderFailure_) {
      result_ = UpdateResult::FAILED;
      failureReported_ = true;
    } else {
      result_ = UpdateResult::COMPLETED;
      completionReported_ = true;
    }
  }
}

void AudioPlayer::stop() {
  if (generator_ != nullptr) {
    generator_->stop();
  }
  releaseResources();
  active_ = false;
  paused_ = false;
  result_ = UpdateResult::IDLE;
}

bool AudioPlayer::pause() {
  if (!active_) {
    return false;
  }
  paused_ = true;
  result_ = UpdateResult::PAUSED;
  return true;
}

bool AudioPlayer::setVolume(uint8_t volume) {
  if (volume > 100) {
    return false;
  }
  volume_ = volume;
  if (output_ != nullptr) {
    output_->SetGain(static_cast<float>(volume_) / 100.0f);
  }
  return true;
}

bool AudioPlayer::isActive() const { return active_; }

bool AudioPlayer::isPaused() const { return paused_; }

AudioPlayer::UpdateResult AudioPlayer::lastResult() const { return result_; }

const char* AudioPlayer::requestId() const { return requestId_; }

const char* AudioPlayer::audioId() const { return audioId_; }

bool AudioPlayer::takeCompleted() {
  const bool value = completionReported_;
  completionReported_ = false;
  return value;
}

bool AudioPlayer::takeFailed() {
  const bool value = failureReported_;
  failureReported_ = false;
  return value;
}

void AudioPlayer::releaseResources() {
  if (generator_ != nullptr) {
    delete generator_;
    generator_ = nullptr;
  }
  if (output_ != nullptr) {
    output_->stop();
    delete output_;
    output_ = nullptr;
  }
  if (buffer_ != nullptr) {
    delete buffer_;
    buffer_ = nullptr;
  }
  if (source_ != nullptr) {
    source_->close();
    delete source_;
    source_ = nullptr;
  }
}

bool AudioPlayer::isWavUrl() const {
  const char* query = strchr(audioUrl_, '?');
  if (query != nullptr && strstr(query, "format=wav") != nullptr) {
    return true;
  }
  const size_t length = query == nullptr ? strlen(audioUrl_) : static_cast<size_t>(query - audioUrl_);
  return length >= 4 && strcasecmp(audioUrl_ + length - 4, ".wav") == 0;
}

void AudioPlayer::onSourceStatus(void* data, int code, const char* message) {
  (void)message;
  auto* player = static_cast<AudioPlayer*>(data);
  if (player == nullptr) {
    return;
  }
  if (code == AudioFileSourceHTTPStream::STATUS_HTTPFAIL ||
      code == AudioFileSourceHTTPStream::STATUS_DISCONNECTED ||
      code == AudioFileSourceHTTPStream::STATUS_NODATA) {
    player->streamFailure_ = true;
  }
}

void AudioPlayer::onDecoderStatus(void* data, int code, const char* message) {
  (void)message;
  auto* player = static_cast<AudioPlayer*>(data);
  if (player != nullptr && code != 0) {
    player->decoderFailure_ = true;
  }
}


