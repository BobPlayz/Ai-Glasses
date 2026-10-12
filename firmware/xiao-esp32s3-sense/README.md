# Candidate XIAO ESP32-S3 Sense firmware

This is candidate firmware, not verified firmware. Do not flash until the exact board/revision and pin map have been checked against the manufacturer's current documentation.

## Features in this candidate
- Joins a private local Wi-Fi network.
- Authenticates to the laptop using the shared .device-token.
- Posts camera/privacy/microphone state to /api/device/status.
- Polls /api/device/command for dashboard camera permission and an explicit visual-question capture request.
- Camera driver remains stopped until both dashboard permission and the physical switch allow it.
- Checks the physical privacy switch before capture and illuminates the external indicator during capture.
- Uploads one JPEG frame (firmware-capped at 1 MiB to avoid large duplicate RAM allocations) to /api/device/capture-result.
- Captures short mono 16 kHz audio chunks from the candidate onboard PDM microphone and sends WAV data to /api/device/audio.
- The laptop performs wake-phrase detection, speech recognition, and local model inference. Speech output uses online neural TTS by default unless the dashboard toggle is disabled, then falls back to cached offline speech when available.

## Wiring assumptions to verify before power-up
- Privacy switch: GPIO 2 to GND means camera capture enabled, using internal pull-up.
- Indicator LED: GPIO 21 through a suitable current-limiting resistor to GND.
- Camera pin map is the candidate XIAO ESP32-S3 Sense mapping in src/main.cpp. The firmware limits frames to 1 MiB because it temporarily builds a multipart upload buffer alongside the camera frame.
- PDM microphone pins: GPIO 42 is clock and GPIO 41 is data. This matches the [official Seeed pin map](https://wiki.seeedstudio.com/xiao_esp32s3_pin_multiplexing/); still verify the exact hardware revision.
- The camera switch gates firmware capture, not electrical power to the sensor. For a stronger physical guarantee, a technician must review a hardware power-gating design.

## Setup
1. Install PlatformIO and the supported ESP32-S3 Arduino toolchain.
2. Copy secrets.example.h to secrets.h.
3. Enter private Wi-Fi credentials, laptop LAN IPv4 address, and token from the laptop .device-token.
4. Run the laptop in LAN mode on the same trusted private network.
5. Compile before connecting hardware, then test over USB power with the camera switch off first.
6. Confirm the actual microphone records cleanly and that the exact camera pin map matches the board before relying on it.

Do not commit secrets.h. HTTP is used on the local LAN, so use only a trusted private network and do not use public Wi-Fi.
