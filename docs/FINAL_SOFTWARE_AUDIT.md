# Final software audit and hardware handoff

## What is implemented

- Windows PowerShell setup creates a Python 3.11 environment, private local pairing credentials, and local model/voice/OCR caches.
- Setup validates cached voice synthesis, local text/vision/OCR services, Python compilation, unit tests, and candidate firmware compilation before writing the setup-complete marker.
- Local Ollama text inference, fallback model, SQLite memory, opt-in conversation summaries, cached multilingual Whisper transcription, offline Piper English/Telugu speech, Tesseract OCR, and local vision adapter.
- Localhost dashboard and optional PIN-protected LAN dashboard.
- Three-control dashboard (AI Core, Vision, Settings), dark/cyan reactor with restrained depth effects, sequential privacy-gated live vision, and advanced settings for connections/permissions/voice/memory.
- Device API uses a private pairing token and serves short cached-Piper WAV responses to the paired device for MAX98357 I2S playback.
- Camera capture defaults off and requires dashboard permission plus the physical privacy switch and indicator status.
- Device microphone defaults off. The dashboard has an explicit opt-in switch, the server rejects audio uploads while disabled, firmware only reads/uploads while permission is active, and in-flight transcription results are discarded if permission is revoked.
- Setup recreates only the project-local .venv if it is missing or is not Python 3.11. Downloads use temporary files and basic size checks to avoid retaining obviously partial voice/OCR assets.
- CI runs Python compilation/unit tests and a separate candidate firmware build.

## Commands after cloning/downloading the repository

Run in PowerShell from the repository root:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\setup.ps1
.\launch.ps1
```

Open http://127.0.0.1:8765.

For phone access on a trusted private network, stop localhost mode and run:

```powershell
.\launch-lan.ps1
```

The script asks for confirmation and uses the generated dashboard PIN. Do not expose the prototype on public/shared Wi-Fi.

## Software smoke test

Before connecting hardware:
1. Ask a text question in the dashboard and confirm a local answer.
2. Test English and Telugu speech from the offline voice panel.
3. Test a chosen image and confirm OCR/vision output.
4. Use the laptop microphone simulator and confirm transcription works.
5. Confirm dashboard camera and device microphone controls both start disabled.
6. Confirm the device microphone endpoint returns HTTP 403 while disabled.
7. Use Settings to check glasses Wi-Fi status, toggle camera/microphone permissions, connect/disconnect the laptop microphone, and test local speech output.
8. Confirm AI Core pause revokes camera/microphone permission and resume does not re-enable either automatically.
9. With the paired board, test one-shot and sequential live vision, then confirm a queued response plays through the MAX98357 when Piper assets are installed.
10. Run `python -m unittest discover -s tests -v` and `pio run -d firmware/xiao-esp32s3-sense` after setup.

## Hardware integration is still unverified

No software-only audit can certify a board that has not been assembled and tested. Before uploading firmware:
- Purchase/confirm the exact Seeed XIAO ESP32-S3 Sense revision and confirm its camera and PDM microphone pin map against the board's official documentation.
- Copy `firmware/xiao-esp32s3-sense/secrets.example.h` to `secrets.h`; set the private Wi-Fi credentials, laptop's LAN IPv4 URL, and contents of the laptop's `.device-token`. Never commit `secrets.h`.
- Verify the physical camera privacy switch and indicator wiring with a qualified adult/technician before powering the assembled setup. Do not improvise battery or charging wiring.
- Compile/upload to the exact board, confirm the device heartbeat, test the physical switch, then explicitly enable camera or microphone from the dashboard only when needed.
- Rehearse the full flow with the internet disconnected after models are cached. Confirm latency, Telugu recognition, and voice quality on the actual laptop.

CI proves the code compiles and automated tests pass; it does not prove hardware behavior, speech quality, or real-time performance on the target laptop.

## Locked-BOM items that still need physical confirmation

The software and candidate firmware are prepared, but a software-only run cannot certify the assembled glasses. The locked BOM does not explicitly list an external camera indicator LED; the existing firmware assumes a camera indicator on GPIO21. Confirm that the exact board's built-in LED is visibly suitable for the intended wearable use, or add a dedicated visible indicator before enabling the camera. Also confirm the woofer's impedance/power rating, amplifier breakout pin labels, power module's protected output, and exact XIAO revision. Do not power the wearable until an experienced adult/technician has checked the circuit, polarity, and shorts.
