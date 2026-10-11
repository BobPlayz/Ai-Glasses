# Development status

This file distinguishes committed code from tested behavior.

## Committed code
- Dashboard UI and local API
- SQLite memory create/list/delete/clear
- Local Ollama client restricted to loopback hosts
- Primary/fallback local text model attempts
- Keyword-based retrieval of relevant saved memory
- Windows setup/launch scripts with optional model caching
- Offline speech transcription adapter using a cached faster-whisper model
- Best-effort local eSpeak NG speech-output adapter
- Local Ollama image-question adapter for an explicitly supplied frame
- Unit tests for memory retrieval and Ollama client

## Not verified on the target Windows laptop
- Python dependency installation
- Ollama installation and model availability
- Speech/vision model caching
- Local model latency and RAM consumption
- Memory persistence under repeated restarts
- Offline operation with internet disconnected
- Telugu voice quality and speech-recognition accuracy

## Not yet integrated end-to-end
- Always-listening microphone loop and custom wake-word detection
- Audio stream from the actual glasses microphone into speech recognition
- Speech output control from the assistant response
- Camera capture request from the glasses board into the vision adapter
- ESP32-S3 firmware, Wi-Fi pairing, and transport protocol
- Hardware-enforced camera privacy switch and capture indicator
- Authenticated phone dashboard and local memory PIN
- Full offline and physical-device tests

Do not mark a feature as complete based only on a committed file. Update this checklist after the corresponding test has actually passed.
