#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include "esp_camera.h"
#include "driver/i2s.h"
#include "secrets.h"

// Candidate firmware for Seeed XIAO ESP32-S3 Sense.
// Not verified against a purchased board. Confirm exact revision and pin map.
static constexpr int PRIVACY_SWITCH_PIN = 2; // switch to GND = capture enabled
static constexpr int CAMERA_INDICATOR_PIN = 21; // external LED + resistor
static constexpr unsigned long STATUS_INTERVAL_MS = 2000;
static constexpr unsigned long COMMAND_INTERVAL_MS = 300;
static constexpr size_t MAX_JPEG_BYTES = 8 * 1024 * 1024;
static constexpr uint32_t MIC_SAMPLE_RATE = 16000;
static constexpr size_t MIC_SAMPLES = 16000; // one second, mono, 16-bit PCM

static unsigned long lastStatus = 0;
static unsigned long lastCommand = 0;
static bool cameraReady = false;
static bool indicatorOn = false;
static bool microphoneReady = false;
static int16_t* microphoneSamples = nullptr;

bool privacySwitchEnabled() {
  return digitalRead(PRIVACY_SWITCH_PIN) == LOW;
}

String apiUrl(const String& path) {
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

bool initMicrophone() {
  i2s_config_t config = {};
  config.mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX | I2S_MODE_PDM);
  config.sample_rate = MIC_SAMPLE_RATE;
  config.bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT;
  config.channel_format = I2S_CHANNEL_FMT_ONLY_LEFT;
  config.communication_format = I2S_COMM_FORMAT_STAND_I2S;
  config.intr_alloc_flags = ESP_INTR_FLAG_LEVEL1;
  config.dma_buf_count = 6;
  config.dma_buf_len = 512;
  config.use_apll = false;
  config.tx_desc_auto_clear = false;
  config.fixed_mclk = 0;

  esp_err_t err = i2s_driver_install(I2S_NUM_0, &config, 0, nullptr);
  if (err != ESP_OK) {
    Serial.printf("Microphone I2S install failed: 0x%x\\n", err);
    return false;
  }
  i2s_pin_config_t pins = {};
  pins.bck_io_num = 41; // candidate onboard PDM microphone clock
  pins.ws_io_num = -1;
  pins.data_out_num = -1;
  pins.data_in_num = 42; // candidate onboard PDM microphone data
  err = i2s_set_pin(I2S_NUM_0, &pins);
  if (err != ESP_OK) {
    Serial.printf("Microphone pin setup failed: 0x%x\\n", err);
    i2s_driver_uninstall(I2S_NUM_0);
    return false;
  }
  microphoneSamples = static_cast<int16_t*>(ps_malloc(MIC_SAMPLES * sizeof(int16_t)));
  if (!microphoneSamples) microphoneSamples = static_cast<int16_t*>(malloc(MIC_SAMPLES * sizeof(int16_t)));
  if (!microphoneSamples) {
    i2s_driver_uninstall(I2S_NUM_0);
    return false;
  }
  return true;
}

void writeLe16(uint8_t* out, uint16_t value) {
  out[0] = value & 0xff;
  out[1] = (value >> 8) & 0xff;
}

void writeLe32(uint8_t* out, uint32_t value) {
  out[0] = value & 0xff;
  out[1] = (value >> 8) & 0xff;
  out[2] = (value >> 16) & 0xff;
  out[3] = (value >> 24) & 0xff;
}

bool sendMicrophoneChunk() {
  if (!microphoneReady || WiFi.status() != WL_CONNECTED || !microphoneSamples) return false;
  size_t filled = 0;
  const size_t targetBytes = MIC_SAMPLES * sizeof(int16_t);
  while (filled < targetBytes) {
    size_t bytesRead = 0;
    esp_err_t err = i2s_read(I2S_NUM_0,
      reinterpret_cast<uint8_t*>(microphoneSamples) + filled,
      targetBytes - filled, &bytesRead, pdMS_TO_TICKS(1200));
    if (err != ESP_OK || bytesRead == 0) return false;
    filled += bytesRead;
  }

  const size_t wavSize = 44 + targetBytes;
  uint8_t* wav = static_cast<uint8_t*>(malloc(wavSize));
  if (!wav) return false;
  memcpy(wav, "RIFF", 4);
  writeLe32(wav + 4, static_cast<uint32_t>(wavSize - 8));
  memcpy(wav + 8, "WAVEfmt ", 8);
  writeLe32(wav + 16, 16);
  writeLe16(wav + 20, 1);
  writeLe16(wav + 22, 1);
  writeLe32(wav + 24, MIC_SAMPLE_RATE);
  writeLe32(wav + 28, MIC_SAMPLE_RATE * 2);
  writeLe16(wav + 32, 2);
  writeLe16(wav + 34, 16);
  memcpy(wav + 36, "data", 4);
  writeLe32(wav + 40, static_cast<uint32_t>(targetBytes));
  memcpy(wav + 44, microphoneSamples, targetBytes);

  HTTPClient http;
  http.begin(apiUrl("/api/device/audio"));
  http.addHeader("X-Device-Token", DEVICE_TOKEN);
  http.addHeader("Content-Type", "audio/wav");
  http.setTimeout(45000);
  int code = http.POST(wav, wavSize);
  String response = code > 0 ? http.getString() : "";
  http.end();
  free(wav);
  if (code == 200) {
    JsonDocument doc;
    if (deserializeJson(doc, response) == DeserializationError::Ok) {
      const char* state = doc["state"] | "unknown";
      Serial.printf("Voice state: %s\\n", state);
      if (doc["wake_detected"] == true) Serial.println("Wake phrase detected. Ask your question in the next audio chunk.");
      if (doc["answer"].is<const char*>()) Serial.printf("Assistant: %s\\n", doc["answer"].as<const char*>());
    }
    return true;
  }
  Serial.printf("Microphone upload returned HTTP %d\\n", code);
  return false;
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
  doc["microphone_ready"] = microphoneReady;
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
  microphoneReady = initMicrophone();
  Serial.printf("Microphone: %s\\n", microphoneReady ? "ready" : "unavailable");
  postStatus();
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    setIndicator(false);
    delay(500);
    return;
  }
  if (!privacySwitchEnabled()) {
    setIndicator(false);
    if (cameraReady) {
      esp_camera_deinit();
      cameraReady = false;
      Serial.println("Privacy switch off: camera driver stopped.");
      postStatus();
    }
  } else if (!cameraReady) {
    cameraReady = initCamera();
    postStatus();
  }

  unsigned long now = millis();
  if (now - lastStatus >= STATUS_INTERVAL_MS) {
    lastStatus = now;
    postStatus();
  }
  if (now - lastCommand >= COMMAND_INTERVAL_MS) {
    lastCommand = now;
    if (privacySwitchEnabled() && cameraReady) checkCommand();
  }
  // Audio is sent as short WAV chunks. The server processes it locally in RAM
  // and deletes temporary files immediately; the firmware never stores audio.
  sendMicrophoneChunk();
}
