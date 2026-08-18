#ifndef MICROPHONE_RECORDER_H
#define MICROPHONE_RECORDER_H

#include <Arduino.h>

#include "config.h"

class MqttManager;

class MicrophoneRecorder {
 public:
  void begin(MqttManager* mqtt);
  bool start(const char* requestId, const char* recordingId, uint32_t durationSeconds);
  void update();
  bool stop();
  bool isRecording() const;
  const char* requestId() const;
  const char* recordingId() const;
  bool takeCompleted();
  bool takeFailed();

 private:
  MqttManager* mqtt_ = nullptr;
  char requestId_[64] = {};
  char recordingId_[64] = {};
  uint32_t startedAt_ = 0;
  uint32_t durationMillis_ = 0;
  uint32_t sequence_ = 0;
  uint32_t sampleCount_ = 0;
  bool active_ = false;
  bool completed_ = false;
  bool failed_ = false;
  bool driverReady_ = false;
  int32_t rawSamples_[MIC_SAMPLES_PER_CHUNK] = {};
  int16_t pcmSamples_[MIC_SAMPLES_PER_CHUNK] = {};

  bool installDriver();
  void releaseDriver();
  void fail();
};

#endif
