# Development status

This file distinguishes committed code from tested behavior.

## Implemented in source
- Local dashboard and API with localhost default and PIN-protected opt-in LAN mode
- SQLite memory save/list/delete/clear
- Privacy-first opt-in short summaries rather than full transcript persistence
- Local Ollama client with strict loopback-host validation and smaller fallback model
- Local multilingual Whisper adapter with cached model reuse
- Offline Windows SAPI/eSpeak speech output adapter
- Local vision adapter for explicit image input
- Explicit device capture queue and JPEG upload endpoint
- Configurable wake phrase, audio chunk transcription, question collection, local inference, and speech output
- Dashboard camera control default-off, plus physical-switch check in candidate firmware
- Candidate XIAO ESP32-S3 Sense camera and PDM microphone firmware
- Python unit tests and GitHub Actions workflows

## Still requires target-machine/hardware validation
- Windows dependency/model installation and RAM/latency benchmark
- Confirm actual Whisper model cache works without internet
- Confirm the installed voice can speak the user's English and Telugu naturally
- Compile candidate firmware against the exact ESP32-S3 board revision
- Confirm the actual camera and microphone pin maps
- Confirm switch and indicator wiring with the device unpowered before assembly
- Live camera, audio, wake phrase, and answer loop over local Wi-Fi
- Offline rehearsal repeated at least three times

No unchecked physical-validation item should be described as tested. A code file, mocked unit test, or CI build is not evidence of successful physical hardware operation.
