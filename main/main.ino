#include "wifi_manager.h"
#include "config.h"
#include "mqtt_manager.h"
#include "audio_player.h"

#include <ArduinoJson.h>

namespace {

WifiManager wifiManager;
MqttManager mqttManager;
AudioPlayer audioPlayer;

// ============================================================
// LED CONFIG
// ============================================================
// LED_PIN nên được khai báo trong config.h.
// Ví dụ:
// #define LED_PIN 2
//
// Nếu bạn chưa muốn thêm vào config.h, có thể tạm dùng:
// const uint8_t LED_PIN = 2;
// ============================================================

bool ledState = false;

bool lastWifiState = false;
bool lastMqttState = false;


// ============================================================
// PUBLISH STATUS
// ============================================================

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
            "{\"device_id\":\"%s\","
            "\"request_id\":\"%s\","
            "\"audio_id\":\"%s\","
            "\"status\":\"%s\"}",
            DEVICE_ID,
            requestId,
            audioId,
            status
        );

    } else {

        snprintf(
            payload,
            sizeof(payload),
            "{\"device_id\":\"%s\","
            "\"request_id\":\"%s\","
            "\"status\":\"%s\"}",
            DEVICE_ID,
            requestId,
            status
        );
    }

    mqttManager.publishStatus(payload);
}


// ============================================================
// PUBLISH ERROR
// ============================================================

void publishError(
    const char* requestId,
    const char* code,
    const char* message
) {
    char payload[240];

    snprintf(
        payload,
        sizeof(payload),
        "{\"device_id\":\"%s\","
        "\"request_id\":\"%s\","
        "\"error_code\":\"%s\","
        "\"message\":\"%s\"}",
        DEVICE_ID,
        requestId == nullptr ? "" : requestId,
        code,
        message
    );

    mqttManager.publishError(payload);
}


// ============================================================
// PUBLISH EVENT
// ============================================================

void publishEvent(
    const char* requestId,
    const char* event,
    const char* audioId = nullptr
) {
    char payload[192];

    snprintf(
        payload,
        sizeof(payload),
        "{\"device_id\":\"%s\","
        "\"request_id\":\"%s\","
        "\"audio_id\":\"%s\","
        "\"event\":\"%s\"}",
        DEVICE_ID,
        requestId == nullptr ? "" : requestId,
        audioId == nullptr ? "" : audioId,
        event
    );

    mqttManager.publishEvent(payload);
}


// ============================================================
// LED CONTROL
// ============================================================

void turnLightOn()
{
    digitalWrite(LED_PIN, HIGH);
    ledState = true;

    Serial.println("[LED] ON");
}


void turnLightOff()
{
    digitalWrite(LED_PIN, LOW);
    ledState = false;

    Serial.println("[LED] OFF");
}


void initializeLed()
{
    pinMode(LED_PIN, OUTPUT);

    // Khi ESP32 khởi động:
    // LED mặc định tắt.
    turnLightOff();

    Serial.print("[LED] Initialized on GPIO ");
    Serial.println(LED_PIN);
}


// ============================================================
// MQTT COMMAND HANDLER
// ============================================================

void onMqttCommand(
    const char* payload,
    size_t length
) {

    JsonDocument command;

    const DeserializationError parseError =
        deserializeJson(command, payload, length);


    // --------------------------------------------------------
    // JSON PARSE ERROR
    // --------------------------------------------------------

    if (parseError) {

        publishError(
            "",
            "INVALID_JSON",
            "Command is not valid JSON"
        );

        return;
    }


    // --------------------------------------------------------
    // GET COMMON FIELDS
    // --------------------------------------------------------

    const char* requestId =
        command["request_id"] | "";

    const char* action =
        command["command"] | "";


    // --------------------------------------------------------
    // REQUIRED FIELDS
    // --------------------------------------------------------

    if (requestId[0] == '\0' || action[0] == '\0') {

        publishError(
            requestId,
            "COMMAND_FIELDS_MISSING",
            "request_id and command are required"
        );

        return;
    }


    // ========================================================
    // STOP AUDIO
    // ========================================================

    if (strcmp(action, "STOP") == 0) {

        audioPlayer.stop();

        publishState(
            requestId,
            "STOPPED"
        );

        return;
    }


    // ========================================================
    // PAUSE AUDIO
    // ========================================================

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


    // ========================================================
    // SET VOLUME
    // ========================================================

    if (strcmp(action, "SET_VOLUME") == 0) {

        const int volume =
            command["volume"] | -1;

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

        publishState(
            requestId,
            "IDLE"
        );

        return;
    }


    // ========================================================
    // PLAY AUDIO
    // ========================================================

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


    // ========================================================
    // LIGHT / LED CONTROL
    // ========================================================

    if (strcmp(action, "LIGHT") == 0) {

        const char* state =
            command["state"] | "";


        // ----------------------------------------------------
        // LIGHT ON
        // ----------------------------------------------------

        if (strcmp(state, "ON") == 0) {

            turnLightOn();

            publishState(
                requestId,
                "LIGHT_ON"
            );

            publishEvent(
                requestId,
                "LIGHT_CHANGED"
            );

            return;
        }


        // ----------------------------------------------------
        // LIGHT OFF
        // ----------------------------------------------------

        if (strcmp(state, "OFF") == 0) {

            turnLightOff();

            publishState(
                requestId,
                "LIGHT_OFF"
            );

            publishEvent(
                requestId,
                "LIGHT_CHANGED"
            );

            return;
        }


        // ----------------------------------------------------
        // INVALID LIGHT STATE
        // ----------------------------------------------------

        publishError(
            requestId,
            "LIGHT_STATE_INVALID",
            "state must be ON or OFF"
        );

        return;
    }


    // ========================================================
    // UNKNOWN COMMAND
    // ========================================================

    publishError(
        requestId,
        "UNKNOWN_COMMAND",
        "Unsupported command"
    );
}

} // namespace


// ============================================================
// SETUP
// ============================================================

void setup()
{
    Serial.begin(115200);

    delay(100);

    Serial.println();
    Serial.println("=================================");
    Serial.println("ESP32 Audio + Light Firmware");
    Serial.println("=================================");


    // --------------------------------------------------------
    // LED
    // --------------------------------------------------------

    initializeLed();


    // --------------------------------------------------------
    // WIFI
    // --------------------------------------------------------

    wifiManager.begin(
        WIFI_SSID,
        WIFI_PASSWORD
    );


    // --------------------------------------------------------
    // MQTT
    // --------------------------------------------------------

    mqttManager.begin(
        MQTT_HOST,
        MQTT_PORT,
        DEVICE_ID,
        MQTT_USERNAME,
        MQTT_PASSWORD,
        onMqttCommand
    );
}


// ============================================================
// LOOP
// ============================================================

void loop()
{
    // --------------------------------------------------------
    // WIFI
    // --------------------------------------------------------

    wifiManager.update();


    // --------------------------------------------------------
    // MQTT + AUDIO
    // --------------------------------------------------------

    if (wifiManager.isConnected()) {

        mqttManager.update();

        audioPlayer.update();
    }


    // --------------------------------------------------------
    // WIFI STATUS CHANGE
    // --------------------------------------------------------

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


    // --------------------------------------------------------
    // MQTT STATUS CHANGE
    // --------------------------------------------------------

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


    // --------------------------------------------------------
    // AUDIO COMPLETED
    // --------------------------------------------------------

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


    // --------------------------------------------------------
    // AUDIO FAILED
    // --------------------------------------------------------

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


    // --------------------------------------------------------
    // SMALL DELAY
    // --------------------------------------------------------

    delay(10);
}