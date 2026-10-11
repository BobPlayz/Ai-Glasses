#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include "esp_camera.h"
#include "secrets.h"

// Candidate firmware for Seeed XIAO ESP32-S3 Sense.
// Not verified against a purchased board. Confirm exact revision and pin map.
static constexpr int PRIVACY_SWITCH_PIN = 2; // switch to GND = capture enabled
static constexpr int CAMERA_INDICATOR_PIN = 21; // external LED + resistor
static constexpr unsigned long STATUS_INTERVAL_MS = 2000;
static constexpr unsigned long COMMAND_INTERVAL_MS = 300;
static constexpr size_t MAX_JPEG_BYTES = 8 * 1024 * 1024;

static unsigned long lastStatus = 0;
static unsigned long lastCommand = 0;
static bool cameraReady = false;
static bool indicatorOn = false;

bool privacySwitchEnabled() {
  return digitalRead(PRIVACY_SWITCH_PIN) == LOW;
}

String apiUrl(const char* path) {
  String base = String(LAPTOP_BASE_URL);
  while (base.endsWith("/")) base.remove(base.length() - 1);
  return base + path;
}

void setIndicator(bool on) {
  indicatorOn = on;
  digitalWrite(CAMERA_INDICATOR_PIN, on ? HIGH : LOW);
}

bool initCamera() {
  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = 15;
  config.pin_d1 = 17;
  config.pin_d2 = 18;
  config.pin_d3 = 16;
  config.pin_d4 = 14;
  config.pin_d5 = 12;
  config.pin_d6 = 11;
  config.pin_d7 = 48;
  config.pin_xclk = 10;
  config.pin_pclk = 13;
  config.pin_vsync = 38;
  config.pin_href = 47;
  config.pin_sccb_sda = 40;
  config.pin_sccb_scl = 39;
  config.pin_pwdn = -1;
  config.pin_reset = -1;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;
  config.frame_size = FRAMESIZE_VGA;
  config.jpeg_quality = 14;
  config.fb_count = 1;
  config.grab_mode = CAMERA_GRAB_WHEN_EMPTY;
  config.fb_location = CAMERA_FB_IN_PSRAM;

  esp_err_t result = esp_camera_init(&config);
  if (result != ESP_OK) {
    Serial.printf("Camera init failed: 0x%x\n", result);
    return false;
  }
  return true;
}

bool postStatus() {
  if (WiFi.status() != WL_CONNECTED) return false;
  HTTPClient http;
  http.begin(apiUrl("/api/device/status"));
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-Device-Token", DEVICE_TOKEN);
  JsonDocument doc;
  doc["board"] = "Seeed XIAO ESP32-S3 Sense candidate";
  doc["connected"] = true;
  doc["camera_enabled"] = cameraReady && privacySwitchEnabled();
  doc["privacy_switch_enabled"] = privacySwitchEnabled();
  doc["indicator_on"] = indicatorOn;
  doc["microphone_ready"] = false;
  doc["firmware_version"] = "0.1-candidate";
  String body;
  serializeJson(doc, body);
  int code = http.POST(body);
  http.end();
  return code >= 200 && code < 300;
}

bool uploadFrame(const String& requestId, camera_fb_t* frame) {
  if (!frame || !frame->buf || frame->len == 0 || frame->len > MAX_JPEG_BYTES) return false;
  if (!privacySwitchEnabled() || !indicatorOn) return false;
  HTTPClient http;
  String boundary = "----AIGlassesBoundary7MA4YWxk";
  String url = apiUrl("/api/device/capture-result?request_id=" + requestId);
  http.begin(url);
  http.addHeader("X-Device-Token", DEVICE_TOKEN);
  String head = "--" + boundary + "\r\nContent-Disposition: form-data; name=\"file\"; filename=\"frame.jpg\"\r\nContent-Type: image/jpeg\r\n\r\n";
  String tail = "\r\n--" + boundary + "--\r\n";
  size_t total = head.length() + frame->len + tail.length();
  uint8_t* body = static_cast<uint8_t*>(malloc(total));
  if (!body) { http.end(); return false; }
  memcpy(body, head.c_str(), head.length());
  memcpy(body + head.length(), frame->buf, frame->len);
  memcpy(body + head.length() + frame->len, tail.c_str(), tail.length());
  http.addHeader("Content-Type", "multipart/form-data; boundary=" + boundary);
  int code = http.sendRequest("POST", body, total);
  free(body);
  http.end();
  return code >= 200 && code < 300;
}

void checkCommand() {
  if (WiFi.status() != WL_CONNECTED) return;
  HTTPClient http;
  http.begin(apiUrl("/api/device/command"));
  http.addHeader("X-Device-Token", DEVICE_TOKEN);
  int code = http.GET();
  if (code != 200) { http.end(); return; }
  String body = http.getString();
  http.end();

  JsonDocument doc;
  if (deserializeJson(doc, body) != DeserializationError::Ok) return;
  if (doc["capture"].isNull()) return;
  String requestId = doc["capture"]["id"] | "";
  if (requestId.isEmpty()) return;
  if (!privacySwitchEnabled() || !cameraReady) {
    Serial.println("Capture ignored: privacy switch is off or camera unavailable.");
    return;
  }

  setIndicator(true);
  postStatus();
  delay(80);
  camera_fb_t* frame = esp_camera_fb_get();
  if (frame) {
    bool uploaded = uploadFrame(requestId, frame);
    esp_camera_fb_return(frame);
    Serial.printf("Capture upload: %s\n", uploaded ? "accepted" : "failed");
  } else {
    Serial.println("Camera returned no frame.");
  }
  setIndicator(false);
  postStatus();
}

void setup() {
  Serial.begin(115200);
  pinMode(PRIVACY_SWITCH_PIN, INPUT_PULLUP);
  pinMode(CAMERA_INDICATOR_PIN, OUTPUT);
  setIndicator(false);

  if (String(WIFI_SSID).startsWith("YOUR_") ||
      String(LAPTOP_BASE_URL).indexOf("192.168.1.25") >= 0 ||
      String(DEVICE_TOKEN).startsWith("PASTE_")) {
    Serial.println("Edit secrets.h before use.");
    while (true) delay(1000);
  }

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("Connecting to local Wi-Fi");
  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < 20000) {
    delay(300);
    Serial.print(".");
  }
  Serial.println();
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("Wi-Fi failed. Reboot after checking credentials.");
    return;
  }
  Serial.print("Device IP: ");
  Serial.println(WiFi.localIP());

  if (privacySwitchEnabled()) {
    cameraReady = initCamera();
  } else {
    Serial.println("Privacy switch is off; camera left uninitialised.");
  }
  postStatus();
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    setIndicator(false);
    delay(500);
    return;
  }
  if (!privacySwitchEnabled()) setIndicator(false);

  unsigned long now = millis();
  if (now - lastStatus >= STATUS_INTERVAL_MS) {
    lastStatus = now;
    postStatus();
  }
  if (now - lastCommand >= COMMAND_INTERVAL_MS) {
    lastCommand = now;
    if (privacySwitchEnabled() && cameraReady) checkCommand();
  }
  delay(10);
}
