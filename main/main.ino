#include "audio_player.h"
#include "config.h"
#include "led_manager.h"
#include "mqtt_manager.h"
#include "wifi_manager.h"

#include <ArduinoJson.h>
#include <string.h>

namespace {

WifiManager wifiManager;
MqttManager mqttManager;
AudioPlayer audioPlayer;
LedManager ledManager(LED_PIN);

bool lastWifiState = false;
bool lastMqttState = false;

void publishState(
    const char* requestId,
    const char* status,
    const char* audioId = nullptr
) {
    char payload[192];

    if (audioId != nullptr) {
        snprintf(
            payload,
            sizeof(payload),
            "{\"device_id\":\"%s\",\"request_id\":\"%s\",\"audio_id\":\"%s\",\"status\":\"%s\"}",
            DEVICE_ID,
            requestId == nullptr ? "" : requestId,
            audioId,
            status
        );
    } else {
        snprintf(
            payload,
            sizeof(payload),
            "{\"device_id\":\"%s\",\"request_id\":\"%s\",\"status\":\"%s\"}",
            DEVICE_ID,
            requestId == nullptr ? "" : requestId,
            status
        );
    }

    mqttManager.publishStatus(payload);
}

void publishError(
    const char* requestId,
    const char* code,
    const char* message
) {
    char payload[240];

    snprintf(
        payload,
        sizeof(payload),
        "{\"device_id\":\"%s\",\"request_id\":\"%s\",\"error_code\":\"%s\",\"message\":\"%s\"}",
        DEVICE_ID,
        requestId == nullptr ? "" : requestId,
        code,
        message
    );

    mqttManager.publishError(payload);
}

void publishEvent(
    const char* requestId,
    const char* event,
    const char* audioId = nullptr
) {
    char payload[192];

    snprintf(
        payload,
        sizeof(payload),
        "{\"device_id\":\"%s\",\"request_id\":\"%s\",\"audio_id\":\"%s\",\"event\":\"%s\"}",
        DEVICE_ID,
        requestId == nullptr ? "" : requestId,
        audioId == nullptr ? "" : audioId,
        event
    );

    mqttManager.publishEvent(payload);
}

void publishLightChanged(
    const char* requestId,
    const char* lightState
) {
    char payload[192];

    snprintf(
        payload,
        sizeof(payload),
        "{\"device_id\":\"%s\",\"request_id\":\"%s\",\"event\":\"LIGHT_CHANGED\",\"light_state\":\"%s\"}",
        DEVICE_ID,
        requestId == nullptr ? "" : requestId,
        lightState
    );

    mqttManager.publishEvent(payload);
}

void onMqttCommand(
    const char* payload,
    size_t length
) {
    JsonDocument command;

    const DeserializationError parseError =
        deserializeJson(command, payload, length);

    if (parseError) {
        publishError(
            "",
            "INVALID_JSON",
            "Command is not valid JSON"
        );
        return;
    }

    const char* requestId =
        command["request_id"] | "";
    const char* action =
        command["command"] | "";

    if (requestId[0] == '\0' || action[0] == '\0') {
        publishError(
            requestId,
            "COMMAND_FIELDS_MISSING",
            "request_id and command are required"
        );
        return;
    }

    if (strcmp(action, "STOP") == 0) {
        audioPlayer.stop();
        publishState(requestId, "STOPPED");
        return;
    }

    if (strcmp(action, "PAUSE") == 0) {
        if (!audioPlayer.pause()) {
            publishError(
                requestId,
                "INVALID_STATE",
                "PAUSE requires an active playback session"
            );
            return;
        }

        publishState(
            requestId,
            "PAUSED",
            audioPlayer.audioId()
        );
        return;
    }

    if (strcmp(action, "SET_VOLUME") == 0) {
        const int volume = command["volume"] | -1;

        if (
            volume < 0 ||
            volume > 100 ||
            !audioPlayer.setVolume(
                static_cast<uint8_t>(volume)
            )
        ) {
            publishError(
                requestId,
                "VOLUME_INVALID",
                "volume must be an integer from 0 to 100"
            );
            return;
        }

        publishState(requestId, "IDLE");
        return;
    }

    if (strcmp(action, "PLAY") == 0) {
        const char* audioId =
            command["audio_id"] | "";
        const char* audioUrl =
            command["audio_url"] | "";

        if (
            audioId[0] == '\0' ||
            audioUrl[0] == '\0'
        ) {
            publishError(
                requestId,
                "PLAY_FIELDS_MISSING",
                "audio_id and audio_url are required"
            );
            return;
        }

        publishState(
            requestId,
            "BUFFERING",
            audioId
        );

        if (
            !audioPlayer.play(
                requestId,
                audioId,
                audioUrl
            )
        ) {
            publishState(
                requestId,
                "ERROR",
                audioId
            );
            publishError(
                requestId,
                "AUDIO_DOWNLOAD_FAILED",
                "Unable to open audio stream"
            );
            audioPlayer.takeFailed();
            return;
        }

        publishState(
            requestId,
            "PLAYING",
            audioId
        );
        return;
    }

    if (strcmp(action, "LIGHT") == 0) {
        const char* state =
            command["state"] | "";

        if (strcmp(state, "ON") == 0) {
            ledManager.turnOn();
            Serial.println("[LED] ON");
            publishLightChanged(requestId, "ON");
            return;
        }

        if (strcmp(state, "OFF") == 0) {
            ledManager.turnOff();
            Serial.println("[LED] OFF");
            publishLightChanged(requestId, "OFF");
            return;
        }

        publishError(
            requestId,
            "LIGHT_STATE_INVALID",
            "state must be ON or OFF"
        );
        return;
    }

    publishError(
        requestId,
        "UNKNOWN_COMMAND",
        "Unsupported command"
    );
}

} // namespace

void setup()
{
    Serial.begin(115200);
    delay(100);

    Serial.println();
    Serial.println("=================================");
    Serial.println("ESP32 Audio + Light Firmware");
    Serial.println("=================================");

    ledManager.begin();

    Serial.print("[LED] Initialized on GPIO ");
    Serial.println(LED_PIN);

    wifiManager.begin(
        WIFI_SSID,
        WIFI_PASSWORD
    );

    mqttManager.begin(
        MQTT_HOST,
        MQTT_PORT,
        DEVICE_ID,
        MQTT_USERNAME,
        MQTT_PASSWORD,
        onMqttCommand
    );
}

void loop()
{
    wifiManager.update();

    if (wifiManager.isConnected()) {
        mqttManager.update();
        audioPlayer.update();
    }

    const bool connected =
        wifiManager.isConnected();

    if (connected != lastWifiState) {
        lastWifiState = connected;
        Serial.println(
            connected
                ? "WiFi: connected"
                : "WiFi: disconnected"
        );
    }

    const bool mqttConnected =
        mqttManager.isConnected();

    if (mqttConnected != lastMqttState) {
        lastMqttState = mqttConnected;
        Serial.println(
            mqttConnected
                ? "MQTT: connected"
                : "MQTT: disconnected"
        );
    }

    if (audioPlayer.takeCompleted()) {
        publishState(
            audioPlayer.requestId(),
            "STOPPED",
            audioPlayer.audioId()
        );

        publishEvent(
            audioPlayer.requestId(),
            "PLAY_COMPLETED",
            audioPlayer.audioId()
        );
    }

    if (audioPlayer.takeFailed()) {
        publishState(
            audioPlayer.requestId(),
            "ERROR",
            audioPlayer.audioId()
        );

        publishError(
            audioPlayer.requestId(),
            "AUDIO_PLAYBACK_FAILED",
            "Audio playback stopped after a stream or decoder failure"
        );
    }

    delay(10);
}
