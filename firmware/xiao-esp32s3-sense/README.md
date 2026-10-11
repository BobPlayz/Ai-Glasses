# Candidate XIAO ESP32-S3 Sense firmware

This is candidate firmware, not verified firmware. Do not flash until the exact board/revision and pin map have been checked against the manufacturer's current documentation.

## Protocol

- Joins a private local Wi-Fi network.
- Authenticates to the laptop using the shared .device-token.
- Posts device state to /api/device/status.
- Polls /api/device/command for an explicit visual-question capture request.
- Checks the physical privacy switch before capture and illuminates the external indicator during capture.
- Uploads one JPEG frame to /api/device/capture-result.

## Wiring assumptions to verify before power-up

- Privacy switch: GPIO 2 to GND means enabled, using internal pull-up.
- Indicator LED: GPIO 21 through a suitable current-limiting resistor to GND.
- Camera pin mapping is the candidate XIAO ESP32-S3 Sense mapping in src/main.cpp.
- Built-in microphone transport is not implemented; firmware reports microphone_ready false.

## Setup

1. Install PlatformIO.
2. Copy secrets.example.h to secrets.h.
3. Enter private Wi-Fi credentials, laptop LAN IPv4 address, and token from the laptop .device-token.
4. Ensure laptop firewall permits the selected port only on the trusted private network.
5. Compile before connecting hardware, then test with USB power and the privacy switch off first.

Do not commit secrets.h. This firmware does not make the physical switch an electrical camera-power disconnect. It enforces the switch in firmware and checks it immediately before capture; a strict hardware-level power cut requires a properly designed camera power-gating circuit with adult/electronics-technician assistance.
