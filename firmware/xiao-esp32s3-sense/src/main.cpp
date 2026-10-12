#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include "esp_camera.h"
#include "driver/i2s.h"
#if __has_include("secrets.h")
#include "secrets.h"
#elif __has_include("../secrets.h")
#include "../secrets.h"
#else
#include "../secrets.example.h"
#endif

// Candidate firmware for Seeed XIAO ESP32-S3 Sense.
// Not verified against a purchased board. Confirm exact revision and pin map.
static constexpr int PRIVACY_SWITCH_PIN = 2; // switch to GND = capture enabled
static constexpr int CAMERA_INDICATOR_PIN = 21; // external LED + resistor
static constexpr unsigned long STATUS_INTERVAL_MS = 2000;
static constexpr unsigned long COMMAND_INTERVAL_MS = 300;
static constexpr size_t MAX_JPEG_BYTES = 1 * 1024 * 1024;
static constexpr uint32_t MIC_SAMPLE_RATE = 16000;
static constexpr size_t MIC_SAMPLES = 32000; // two seconds, mono, 16-bit PCM
static constexpr int SPEAKER_BCLK_PIN = 4; // XIAO D3
static constexpr int SPEAKER_LRCLK_PIN = 5; // XIAO D4
static constexpr int SPEAKER_DATA_PIN = 6; // XIAO D5
static constexpr size_t MAX_SPEECH_BYTES = 900000;

static unsigned long lastStatus = 0;
static unsigned long lastCommand = 0;
static bool cameraReady = false;
static bool indicatorOn = false;
static bool microphoneReady = false;
static bool dashboardCameraAllowed = false;
static volatile bool dashboardMicrophoneAllowed = false; // Server opt-in defaults to false.
static int16_t* microphoneSamples = nullptr;
static bool speakerReady = false;

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
    Serial.printf("Microphone I2S install failed: 0x%x\n", err);
    return false;
  }
  i2s_pin_config_t pins = {};
  pins.bck_io_num = I2S_PIN_NO_CHANGE;
  pins.ws_io_num = 42; // XIAO Sense PDM microphone clock
  pins.data_out_num = I2S_PIN_NO_CHANGE;
  pins.data_in_num = 41; // XIAO Sense PDM microphone data
  err = i2s_set_pin(I2S_NUM_0, &pins);
  if (err != ESP_OK) {
    Serial.printf("Microphone pin setup failed: 0x%x\n", err);
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
  if (!microphoneReady || !dashboardMicrophoneAllowed || WiFi.status() != WL_CONNECTED || !microphoneSamples) return false;
  size_t filled = 0;
  const size_t targetBytes = MIC_SAMPLES * sizeof(int16_t);
  while (filled < targetBytes) {
    // Abort promptly when dashboard permission is revoked, including mid-chunk.
    if (!dashboardMicrophoneAllowed || WiFi.status() != WL_CONNECTED) return false;
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

  // Recheck permission immediately before any microphone data leaves the board.
  if (!dashboardMicrophoneAllowed || WiFi.status() != WL_CONNECTED) { free(wav); return false; }
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
      Serial.printf("Voice state: %s\n", state);
      if (doc["wake_detected"] == true) Serial.println("Wake phrase detected. Ask your question in the next audio chunk.");
      if (doc["answer"].is<const char*>()) Serial.printf("Assistant: %s\n", doc["answer"].as<const char*>());
    }
    return true;
  }
  Serial.printf("Microphone upload returned HTTP %d\n", code);
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
  // The switch can change while the JPEG is being prepared. Check again at
  // the final point before the frame leaves the board.
  if (!privacySwitchEnabled() || !indicatorOn) {
    free(body);
    http.end();
    return false;
  }
  int code = http.sendRequest("POST", body, total);
  free(body);
  http.end();
  return code >= 200 && code < 300;
}

uint16_t readLe16(const uint8_t* p) { return static_cast<uint16_t>(p[0]) | (static_cast<uint16_t>(p[1]) << 8); }
uint32_t readLe32(const uint8_t* p) { return static_cast<uint32_t>(p[0]) | (static_cast<uint32_t>(p[1]) << 8) | (static_cast<uint32_t>(p[2]) << 16) | (static_cast<uint32_t>(p[3]) << 24); }

bool playWavBuffer(const uint8_t* wav, size_t length) {
  if (!speakerReady || !wav || length < 44 || length > MAX_SPEECH_BYTES || memcmp(wav, "RIFF", 4) != 0 || memcmp(wav + 8, "WAVE", 4) != 0) return false;
  uint16_t channels = 0, bits = 0, format = 0;
  uint32_t sampleRate = 0, dataLength = 0;
  const uint8_t* pcm = nullptr;
  size_t offset = 12;
  while (offset + 8 <= length) {
    uint32_t chunkSize = readLe32(wav + offset + 4);
    size_t chunkStart = offset + 8;
    if (chunkSize > length - chunkStart) return false;
    if (memcmp(wav + offset, "fmt ", 4) == 0 && chunkSize >= 16) {
      format = readLe16(wav + chunkStart);
      channels = readLe16(wav + chunkStart + 2);
      sampleRate = readLe32(wav + chunkStart + 4);
      bits = readLe16(wav + chunkStart + 14);
    } else if (memcmp(wav + offset, "data", 4) == 0) {
      pcm = wav + chunkStart;
      dataLength = chunkSize;
    }
    offset = chunkStart + chunkSize + (chunkSize & 1);
  }
  if (format != 1 || channels != 1 || bits != 16 || sampleRate < 16000 || sampleRate > 48000 || !pcm || !dataLength || dataLength > length) return false;
  i2s_driver_uninstall(I2S_NUM_1);
  i2s_config_t config = {};
  config.mode = static_cast<i2s_mode_t>(I2S_MODE_MASTER | I2S_MODE_TX);
  config.sample_rate = sampleRate;
  config.bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT;
  config.channel_format = I2S_CHANNEL_FMT_ONLY_LEFT;
  config.communication_format = I2S_COMM_FORMAT_STAND_I2S;
  config.intr_alloc_flags = ESP_INTR_FLAG_LEVEL1;
  config.dma_buf_count = 8;
  config.dma_buf_len = 512;
  config.use_apll = false;
  config.tx_desc_auto_clear = true;
  config.fixed_mclk = 0;
  if (i2s_driver_install(I2S_NUM_1, &config, 0, nullptr) != ESP_OK) return false;
  i2s_pin_config_t pins = {};
  pins.bck_io_num = SPEAKER_BCLK_PIN;
  pins.ws_io_num = SPEAKER_LRCLK_PIN;
  pins.data_out_num = SPEAKER_DATA_PIN;
  pins.data_in_num = I2S_PIN_NO_CHANGE;
  if (i2s_set_pin(I2S_NUM_1, &pins) != ESP_OK) { i2s_driver_uninstall(I2S_NUM_1); return false; }
  size_t offsetBytes = 0;
  while (offsetBytes < dataLength) {
    size_t written = 0;
    esp_err_t err = i2s_write(I2S_NUM_1, pcm + offsetBytes, dataLength - offsetBytes, &written, pdMS_TO_TICKS(3000));
    if (err != ESP_OK || written == 0) { i2s_driver_uninstall(I2S_NUM_1); return false; }
    offsetBytes += written;
  }
  i2s_zero_dma_buffer(I2S_NUM_1);
  i2s_driver_uninstall(I2S_NUM_1);
  return true;
}

bool fetchAndPlaySpeech() {
  if (WiFi.status() != WL_CONNECTED || !speakerReady) return false;
  HTTPClient http;
  http.begin(apiUrl("/api/device/speech"));
  http.addHeader("X-Device-Token", DEVICE_TOKEN);
  http.setTimeout(15000);
  int code = http.GET();
  if (code != 200) { http.end(); return false; }
  int declaredSize = http.getSize();
  if (declaredSize <= 44 || static_cast<size_t>(declaredSize) > MAX_SPEECH_BYTES) { http.end(); return false; }
  uint8_t* buffer = static_cast<uint8_t*>(malloc(static_cast<size_t>(declaredSize)));
  if (!buffer) { http.end(); return false; }
  WiFiClient* stream = http.getStreamPtr();
  size_t received = stream->readBytes(buffer, static_cast<size_t>(declaredSize));
  http.end();
  bool played = received == static_cast<size_t>(declaredSize) && playWavBuffer(buffer, received);
  free(buffer);
  Serial.printf("Glasses speaker: %s\n", played ? "played response" : "audio unavailable / incompatible WAV");
  return played;
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
  dashboardCameraAllowed = doc["camera_allowed"] | false;
  dashboardMicrophoneAllowed = doc["microphone_allowed"] | false;
  if (doc["speech_pending"] == true) fetchAndPlaySpeech();
  if (!dashboardCameraAllowed || !privacySwitchEnabled()) {
    if (cameraReady) {
      esp_camera_deinit();
      cameraReady = false;
      postStatus();
    }
    return;
  }
  if (!cameraReady) {
    cameraReady = initCamera();
    postStatus();
  }
  if (doc["capture"].isNull()) return;
  String requestId = doc["capture"]["id"] | "";
  if (requestId.isEmpty() || !cameraReady) return;

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

void microphoneTask(void* parameter) {
  for (;;) {
    if (microphoneReady && dashboardMicrophoneAllowed && WiFi.status() == WL_CONNECTED) {
      sendMicrophoneChunk();
    }
    vTaskDelay(pdMS_TO_TICKS(20));
  }
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

  // Camera remains uninitialised until BOTH the dashboard control and physical
  // switch allow it. The server sends camera_allowed=false by default.
  Serial.println("Camera is disabled until dashboard control and physical switch allow it.");
  // Speaker TX uses I2S_NUM_1 and exposed GPIO4/5/6; PDM mic remains on I2S_NUM_0.
  speakerReady = true;
  microphoneReady = initMicrophone();
  Serial.printf("Microphone: %s\n", microphoneReady ? "ready" : "unavailable");
  postStatus();
  if (microphoneReady) {
    xTaskCreatePinnedToCore(microphoneTask, "glasses-mic", 8192, nullptr, 1, nullptr, 0);
  }
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    setIndicator(false);
    dashboardCameraAllowed = false;
    dashboardMicrophoneAllowed = false;
    if (cameraReady) { esp_camera_deinit(); cameraReady = false; }
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
  }

  unsigned long now = millis();
  if (now - lastStatus >= STATUS_INTERVAL_MS) {
    lastStatus = now;
    postStatus();
  }
  if (now - lastCommand >= COMMAND_INTERVAL_MS) {
    lastCommand = now;
    checkCommand();
  }
  // Audio streaming runs in a separate task so camera polling remains responsive.
}
