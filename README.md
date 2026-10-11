# AI Glasses

A local-first smart-glasses prototype for a school exhibition. The Windows laptop is the AI host; the candidate physical controller is the Seeed XIAO ESP32-S3 Sense. The board has not been confirmed as purchased or physically tested.

## Included in this repository

- Futuristic dark/cyan local dashboard
- Connections hub for glasses Wi-Fi link status, camera/microphone permission toggles, laptop microphone connect/disconnect, and local speaker test
- Local Ollama text assistant with primary and fallback models
- SQLite useful-fact memory and opt-in short conversation summaries
- Offline multilingual Whisper transcription adapter and cached-model setup
- Cached Piper neural speech in British English and Telugu, with Windows SAPI/eSpeak fallback
- Local Tesseract OCR using English and Telugu language data
- Local vision adapter for an explicitly supplied image, combined with OCR results
- Dashboard camera enable/disable control, default off
- Explicit device microphone enable/disable control, default off, with server-side upload rejection until opted in
- Device API with pairing token, camera command queue, and one-shot JPEG upload
- Candidate ESP32-S3 camera, privacy-switch, indicator, and microphone firmware
- Configurable wake phrase and local audio chunk processing
- Local-only mode and optional PIN-protected LAN dashboard mode
- Unit tests and GitHub Actions checks

## Requirements

- Windows 10 or 11 (64-bit; Python 3.11 is required)
- Python 3.11
- Internet for first-time dependencies and model caching
- Ollama
- For physical glasses: compatible ESP32-S3 camera/microphone board, USB cable, switch, indicator LED and resistor, safe mounting, and wiring verified for the exact board revision
- Tesseract OCR engine, installed by setup

## Setup

From PowerShell in the repository directory:

    Set-ExecutionPolicy -Scope Process Bypass
    .\setup.ps1

Setup creates the Python environment, installs dependencies, creates a private dashboard PIN and device pairing token, downloads and verifies the local speech/OCR assets, pulls the Ollama models, compiles the candidate firmware, and runs the software checks. The first run needs internet and can take a while because the model files are large. Keep the PIN and token private. If Ollama was installed during setup but is not available in the current shell, reopen PowerShell and rerun setup to finish model caching.

For an existing setup, install and verify the offline male English and Telugu voices without repeating all model downloads:

    powershell -ExecutionPolicy Bypass -File .\scripts\install_british_voice.ps1

### Offline speech

Speech uses cached Piper neural voices: male Alan for British English and the male Venkatesh voice for Telugu. Speech generation runs locally and requires no API key, subscription, or cloud TTS service. English can fall back to an installed Windows voice if Piper is unavailable; Telugu intentionally reports a failure rather than mispronouncing Telugu through an English voice.

For laptop-only mode:

    .\launch.ps1

Open http://127.0.0.1:8765.

For phone access on a trusted private Wi-Fi network:

    .\launch-lan.ps1

Find the laptop IPv4 address using ipconfig, then open http://LAPTOP-IP:8765 on the phone. Enter the generated dashboard PIN. Do not use public/shared Wi-Fi; this prototype's device protocol uses HTTP on the trusted LAN.

## Models

- Text primary: qwen2.5:1.5b
- Text fallback: qwen2.5:0.5b
- Speech: faster-whisper base multilingual model
- Vision candidate: moondream:1.8b
- OCR: local Tesseract with eng+tel data
- TTS: Piper en_GB-alan-medium British English and te_IN-venkatesh-medium Telugu voices

These are configuration candidates. Actual model latency, memory pressure, Telugu recognition quality, and voice availability must be verified on the target laptop. The app never downloads models while answering a question. On an 8 GB laptop, close memory-heavy apps during first model loads; local vision inference may be slower than text chat.

## Privacy defaults

- Dashboard camera control starts disabled.
- Capture requires a visual question, dashboard camera control enabled, a connected device, and the physical switch enabled.
- Firmware turns on the capture indicator while obtaining a frame and stops the camera driver when the dashboard control or physical switch disables it.
- Device microphone is disabled by default. Audio capture/upload starts only after explicit dashboard opt-in; the laptop server rejects device audio while disabled, and firmware stops reading/uploading when the permission is revoked. When enabled, short audio chunks are sent to this laptop for local processing. Temporary WAV files are deleted after processing; recognized transcripts are not saved unless the user explicitly asks to save a summary.
- Memory is local and can be inspected or cleared.
- The dashboard is localhost-only by default. LAN mode requires the generated PIN.
- Device credentials, PINs, local memory, recordings, and model files are excluded from Git.

A firmware-controlled switch is not an electrical camera power disconnect. Review the wiring with a qualified adult/technician before assembly. Do not improvise lithium battery or charging circuits.

## Tests and status

Run Python checks with:

    .\.venv\Scripts\python.exe -m compileall laptop tests
    .\.venv\Scripts\python.exe -m unittest discover -s tests -v

The API privacy tests cover default-off camera/microphone permissions, microphone upload rejection, dashboard opt-in/revocation, and device-token enforcement.

Firmware compile check:

    pio run -d firmware/xiao-esp32s3-sense

Committed code and CI checks do not certify that the selected board works physically. Do not claim the full offline demo is verified until it has been rehearsed with the internet disconnected and the exact hardware.
