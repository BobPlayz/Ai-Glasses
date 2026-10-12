# AI-Spects integration status

This document separates what the repository already does from what still needs hardware-aware integration. A successful Python/firmware build is not proof that the assembled glasses work.

## Requested component set

| Component | Role | Integration note |
|---|---|---|
| Virtual Pathshala XIAO ESP32-S3 Sense | camera + onboard PDM microphone + controller | firmware target; verify exact revision and camera/mic pinout before flashing |
| Roboduino MAX98357 I2S amplifier | digital audio amplifier | candidate firmware implements I2S BCLK/LRCLK/DATA output on GPIO 4/5/6; physical wiring and playback remain unverified |
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

- The laptop app already supports local Ollama text inference, local image description, English/Telugu OCR, online neural speech by default with offline fallback, a browser dashboard, device pairing, and privacy-gated XIAO JPEG snapshot uploads.
- The XIAO firmware currently uploads short WAV microphone chunks only when dashboard microphone permission is enabled.
- Visual questions request a single JPEG snapshot through the device command queue. The current XIAO firmware is **not** a continuous video streamer.
- Speech responses play through the laptop's audio output, and the software/firmware now include a bounded paired-device WAV queue and candidate I2S playback path for the MAX98357 + woofer. Actual glasses-speaker playback is **not yet physically verified**.
- Added `laptop/vision/live_stream.py` supplies a bounded, private-LAN MJPEG reader and throttled local vision inference for a source that actually exposes an MJPEG stream. It accepts still images through `describe_image`. The helper is not yet wired into the dashboard and is not an MJPEG server for the XIAO.

## Required next implementation steps

1. Diagnose the outstanding phone-image-to-local-vision path using the existing application-level tests and safe per-attempt diagnostics. The previous direct model test succeeded, but the dashboard phone-camera route has not yet passed its end-to-end acceptance test.
2. Run the paired-device audio path on the exact board: verify bounded WAV retrieval, I2S pin mapping, amplifier input labels, speaker impedance/power, and that laptop playback remains available when device audio fails.
3. Verify the camera switch and visible indicator on the exact board revision. The firmware switch is a software gate, not an electrical camera power disconnect.
4. Complete a full laptop rehearsal with internet disconnected after caching all required models and voices. Record observed latency and whether English/Telugu speech and vision succeed.
5. Bench-test over USB first, with an experienced adult/technician checking polarity, speaker load, solder joints, and shorts. Do not connect a wearable battery/power module until the power path is verified.
6. Keep CI checks green and add regressions for every new failure discovered during real-device tests. A compile or unit-test pass does not certify physical behavior.

## Completion gate

The requested experience is complete only when live frames reach local inference, a still image can be analyzed from the dashboard, device-mic input is permission-gated, spoken responses are heard from the glasses speaker, and the dashboard reports real device/model/audio status. Until then, describe the build as software-prepared, not hardware-verified.


## Dashboard simplification and live vision

The existing dark/cyan reactor design is retained and amplified with a subtle perspective grid and ambient depth lighting. The primary screen has three controls: AI Core, Vision, and Settings. Unconfigured Inbox/GitHub buttons are removed, and the detailed camera, microphone, voice, and memory controls are tucked behind Settings. Pausing AI Core revokes camera and device-microphone permissions; resuming does not re-enable them automatically.

Live vision uses sequential one-shot frames and local inference, rather than claiming a high-frame-rate raw video stream. It is gated by dashboard camera permission, the paired-device token, and the physical privacy switch. No hardware test is claimed before the exact components are purchased and assembled.


## Local glasses-speaker path

- Typed assistant answers, manual speech, and paired-microphone answers can enqueue short WAV audio for the paired device. With online voice enabled, synthesis sends spoken text to the online speech provider; turning it off selects local Piper fallback.
- The authenticated device polls for a queued WAV. The server bounds audio to 900,000 bytes and expires the queue after 30 seconds. If speech synthesis fails, laptop text remains available and no glasses audio is queued.
- Candidate I2S output uses GPIO4 (BCLK), GPIO5 (LRCLK/WS), and GPIO6 (DATA), corresponding to XIAO D3/D4/D5. The onboard PDM microphone remains on GPIO41/42 using I2S_NUM_0. Confirm the exact board revision and amplifier breakout labels before wiring.
- The MAX98357 I2S amplifier needs a suitable speaker load and documented supply. Confirm the selected 2-inch woofer's impedance and power rating from its actual label/listing before power-up. Never connect the amplifier's bridged speaker outputs to ground or to a board GPIO.
- The physical speaker, wiring, exact component compatibility, firmware upload, audio quality, and battery/power path remain unverified until parts are available and bench-tested with an experienced adult/technician.


## Streaming voice responses

The dashboard consumes a token stream from local Ollama. It updates answer text as tokens arrive and synthesizes completed sentences, with a word-boundary fallback for long sentences, while generation continues. This reduces the wait for first audio without chopping every comma into a separate clip. Each generated WAV is played on the laptop and also placed in a bounded FIFO queue for the paired glasses speaker. Speech is phrase-level rather than word-by-word so prosody can stay coherent.

Online neural speech is enabled by default on a fresh setup; the dashboard warms the selected voice, schedules phrase audio in the browser, and queues generated WAVs for the glasses speaker. Disable online speech to use the cached Piper `en_GB-alan-medium` English and `te_IN-venkatesh-medium` Telugu voices. Install offline voices with `scripts\\install_british_voice.ps1`. Spoken text is sent to the online speech provider while online mode is enabled. If the Piper model files are missing, the streaming voice endpoint reports the missing local voice instead of silently claiming that speech worked. The legacy one-shot response endpoint remains available.
