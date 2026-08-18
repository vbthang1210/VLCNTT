#ifndef MICROPHONE_STREAMER_H
#define MICROPHONE_STREAMER_H

#include <Arduino.h>
#include <ESP_I2S.h>

#include "mqtt_manager.h"

class MicrophoneStreamer {
 public:
  MicrophoneStreamer();

  bool begin();
  bool isReady() const;
  void update(MqttManager& mqtt, bool allowCapture);

 private:
  I2SClass i2s_;
  bool ready_ = false;
  uint32_t nextCaptureAt_ = 0;
  uint32_t sessionCounter_ = 0;

  bool captureWindow(MqttManager& mqtt);
  static void convertToPcm16(const int32_t* input,
                             int16_t* output,
                             size_t samples);
};

#endif
