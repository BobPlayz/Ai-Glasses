# Development status

This file distinguishes committed code from tested behavior.

## Committed in repository
- Dashboard UI and local API
- SQLite memory create/list/delete/clear
- Local Ollama client restricted to loopback addresses
- Primary/fallback text model attempt
- Keyword-based retrieval of relevant saved memory
- Windows setup/launch scripts
- Initial unit tests for memory retrieval and Ollama client

## Not yet verified on the target Windows laptop
- Python dependency installation
- Ollama installation and model availability
- Local model latency and RAM consumption
- Persistence behavior under repeated restarts
- Offline operation with internet disconnected

## Not yet implemented
- Local wake-word detection and always-listening microphone loop
- Offline speech recognition for English and Andhra Telugu
- Offline speech synthesis
- Vision/OCR pipeline connected to a camera frame
- ESP32-S3 firmware and Wi-Fi pairing
- Hardware-enforced camera privacy switch and indicator
- Authenticated phone dashboard
- PIN-protected memory UI

Do not mark a feature as complete based only on a committed file. Update this checklist after the corresponding test has actually passed.
