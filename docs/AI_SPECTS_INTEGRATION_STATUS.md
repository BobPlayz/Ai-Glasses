# AI-Spects integration status

This document separates what the repository already does from what still needs hardware-aware integration. A successful Python/firmware build is not proof that the assembled glasses work.

## Requested component set

| Component | Role | Integration note |
|---|---|---|
| Virtual Pathshala XIAO ESP32-S3 Sense | camera + onboard PDM microphone + controller | firmware target; verify exact revision and camera/mic pinout before flashing |
| Roboduino MAX98357 I2S amplifier | digital audio amplifier | requires I2S BCLK, LRCLK, and DATA from the ESP32; speaker output is not implemented in current firmware |
| Electronic Spices 2-inch woofer speaker | response audio | confirm speaker impedance/power rating matches the amplifier module |
| Electronic Spices 5 V mobile power bank module | portable supply | use only its documented protected output; do not improvise battery/charging wiring |
| Ambrane USB-C data cable | setup/programming | confirm it is a data cable, not charge-only |
| Raybloc UV glasses frame | wearable mounting | use a removable mount; do not put board weight or sharp leads against skin |
| Themisto soldering kit/pad/solder | assembly | solder only with adult supervision and ventilation |
| Rpi shop heat-shrink | insulation | insulate every exposed solder joint |
| APTECH DEALS multimeter | checks | verify continuity and supply polarity before connecting modules |
| Electronic Spices 220-ohm resistors | indicator current limiting | use only for a suitable LED circuit, not as a speaker or power resistor |
| Five red SPST switches | user controls | define one as camera privacy control; verify switch wiring before power-up |
| Lalitha 400-point breadboard + jumpers | prototyping | suitable for temporary signal tests, not a secure wearable final mount |
| ElectroBot male headers | removable connections | check pitch and board compatibility |

## Current software behavior

- The laptop app already supports local Ollama text inference, local image description, English/Telugu OCR, offline speech synthesis, a browser dashboard, device pairing, and privacy-gated XIAO JPEG snapshot uploads.
- The XIAO firmware currently uploads short WAV microphone chunks only when dashboard microphone permission is enabled.
- Visual questions request a single JPEG snapshot through the device command queue. The current XIAO firmware is **not** a continuous video streamer.
- Speech responses currently play through the laptop's audio output. The MAX98357 + woofer are **not yet wired into the response path**.
- Added `laptop/vision/live_stream.py` supplies a bounded, private-LAN MJPEG reader and throttled local vision inference for a source that actually exposes an MJPEG stream. It accepts still images through `describe_image`. The helper is not yet wired into the dashboard and is not an MJPEG server for the XIAO.

## Required next implementation steps

1. Keep snapshot mode as the known-safe baseline. Add a dashboard live-analysis toggle that requests frames repeatedly through the existing privacy-gated device queue, throttles inference (start at one frame every 2 seconds), and stops immediately when either privacy control is disabled.
2. Add a speaker-response queue: local TTS must render a bounded PCM/WAV response, the authenticated device endpoint must deliver it only to the paired board, and firmware must play it over a second I2S interface for the MAX98357. Keep laptop-speaker playback as a fallback.
3. Choose and document non-conflicting I2S output pins only after checking the exact XIAO revision and the camera/microphone wiring. The current microphone uses the existing I2S peripheral configuration; output should use a separate peripheral where supported.
4. Enforce limits on audio response size and duration; never accept arbitrary URLs, unauthenticated audio, or public-network stream sources.
5. Add unit tests for camera-stop behavior, speaker queue authorization, audio size/duration limits, and permission revocation during capture/playback.
6. Bench-test over USB first, with a multimeter and an experienced adult checking supply polarity, speaker impedance, solder joints, and shorts. Do not attach the power module to the wearable until the power path is verified.
7. Run setup, Python tests, firmware compile, then test on the exact physical board. Finally cache models/voices and rehearse with internet disconnected.

## Completion gate

The requested experience is complete only when live frames reach local inference, a still image can be analyzed from the dashboard, device-mic input is permission-gated, spoken responses are heard from the glasses speaker, and the dashboard reports real device/model/audio status. Until then, describe the build as software-prepared, not hardware-verified.


## Dashboard simplification and live vision

The existing dark/cyan reactor design is retained and amplified with a subtle perspective grid and ambient depth lighting. The primary screen has three controls: AI Core, Vision, and Settings. Unconfigured Inbox/GitHub buttons are removed, and the detailed camera, microphone, voice, and memory controls are tucked behind Settings. Pausing AI Core revokes camera and device-microphone permissions; resuming does not re-enable them automatically.

Live vision uses sequential one-shot frames and local inference, rather than claiming a high-frame-rate raw video stream. It is gated by dashboard camera permission, the paired-device token, and the physical privacy switch. No hardware test is claimed before the exact components are purchased and assembled.


## Local glasses-speaker path

- Typed assistant answers, manual offline speech, and paired-microphone answers can enqueue short offline Piper WAV audio for the paired device.
- The authenticated device polls for a queued WAV. The server bounds audio to 900,000 bytes and expires the queue after 30 seconds. If Piper assets are unavailable, the laptop-output path remains available and no glasses audio is queued.
- Candidate I2S output uses GPIO4 (BCLK), GPIO5 (LRCLK/WS), and GPIO6 (DATA), corresponding to XIAO D3/D4/D5. The onboard PDM microphone remains on GPIO41/42 using I2S_NUM_0. Confirm the exact board revision and amplifier breakout labels before wiring.
- The MAX98357 I2S amplifier needs a suitable speaker load and documented supply. Confirm the selected 2-inch woofer's impedance and power rating from its actual label/listing before power-up. Never connect the amplifier's bridged speaker outputs to ground or to a board GPIO.
- The physical speaker, wiring, exact component compatibility, firmware upload, audio quality, and battery/power path remain unverified until parts are available and bench-tested with an experienced adult/technician.
