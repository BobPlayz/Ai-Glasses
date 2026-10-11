# AI Glasses

A local-first smart-glasses prototype for a school exhibition. The Windows laptop is the AI host; the ESP32-S3 camera/microphone board is planned but not yet purchased or verified.

## Honest feature status

- [x] Dashboard scaffold and local SQLite memory CRUD
- [x] Local Ollama API client with local-host restriction
- [x] Primary/fallback local model selection and keyword memory retrieval
- [x] Windows setup/launch scripts
- [ ] Install and benchmark Ollama models on the actual laptop
- [ ] Offline English/Telugu speech recognition and wake word
- [ ] Offline text-to-speech
- [ ] Local vision and OCR
- [ ] ESP32-S3 firmware, camera/microphone transport, physical privacy switch
- [ ] Authenticated phone dashboard
- [ ] Full offline and physical-device tests

Unchecked items are not working features. Code committed does not mean tested on the target laptop.

## Requirements

- Windows 11
- Python 3.11
- Internet during initial dependency/model downloads
- Ollama for local LLM answers

## Setup

In PowerShell, from the repository folder:

    Set-ExecutionPolicy -Scope Process Bypass
    .\setup.ps1

The setup script installs Python dependencies, offers to install Ollama, and asks before downloading the primary and fallback models. Downloads may take time and several GB. After setup finishes:

    .\launch.ps1

Open http://127.0.0.1:8765. Questions are processed through local Ollama only; no cloud model endpoint is used. Before testing offline, cache both models and verify with ollama list, then disconnect internet and test.

## Security and privacy

- The dashboard binds to localhost only.
- Do not expose the dashboard to Wi-Fi until authentication and access controls are implemented.
- SQLite data stays on this laptop in the data folder.
- Do not commit conversation memory, recordings, photos, model files, API keys, or other secrets.
- Raw audio recording is not implemented and must remain off by default.
- Camera capture and the physical privacy switch are not implemented yet.
- This repository may be public. Use GitHub Settings > General > Danger Zone > Change repository visibility > Private if you want it restricted.

## Layout

- laptop/app.py: dashboard and API
- laptop/assistant/ollama_client.py: local model client
- laptop/memory/store.py: local memory retrieval
- setup.ps1, launch.ps1: Windows scripts
- docs/: architecture, privacy, hardware, model setup, and test plan
- firmware/: reserved for ESP32-S3 firmware

Label features as implemented, tested on laptop, or tested with physical glasses. Hardware and offline claims require actual tests.
