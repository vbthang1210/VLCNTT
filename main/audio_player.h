#ifndef AUDIO_PLAYER_H
#define AUDIO_PLAYER_H

#include <Arduino.h>

class AudioFileSourceHTTPStream;
class AudioFileSourceBuffer;
class AudioGenerator;
class AudioOutputI2S;

class AudioPlayer {
 public:
  enum class UpdateResult : uint8_t { IDLE, PLAYING, PAUSED, COMPLETED, FAILED };

  bool play(const char* requestId, const char* audioId, const char* audioUrl);
  void update();
  void stop();
  bool pause();
  bool setVolume(uint8_t volume);
  bool isActive() const;
  bool isPaused() const;
  UpdateResult lastResult() const;
  const char* requestId() const;
  const char* audioId() const;
  bool takeCompleted();
  bool takeFailed();

 private:
  AudioFileSourceHTTPStream* source_ = nullptr;
  AudioFileSourceBuffer* buffer_ = nullptr;
  AudioGenerator* generator_ = nullptr;
  AudioOutputI2S* output_ = nullptr;
  char requestId_[64] = {};
  char audioId_[64] = {};
  char audioUrl_[256] = {};
  uint8_t volume_ = 100;
  UpdateResult result_ = UpdateResult::IDLE;
  bool active_ = false;
  bool paused_ = false;
  bool completionReported_ = false;
  bool failureReported_ = false;
  bool streamFailure_ = false;
  bool decoderFailure_ = false;

  void releaseResources();
  bool isWavUrl() const;
  static void onSourceStatus(void* data, int code, const char* message);
  static void onDecoderStatus(void* data, int code, const char* message);
};

#endif
