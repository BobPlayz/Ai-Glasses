# AI Glasses

A local-first smart-glasses prototype for a school exhibition. The Windows laptop is the planned AI host; an ESP32-S3 camera/microphone board is not yet purchased or verified.

## Current status

- [x] Initial laptop dashboard and local SQLite memory scaffold
- [ ] Local language model integration
- [ ] English/Telugu speech recognition and offline speech output
- [ ] Vision/OCR model integration
- [ ] ESP32-S3 firmware and camera/microphone transport
- [ ] Physical privacy switch and capture indicator integration
- [ ] Phone dashboard access with authentication
- [ ] Full offline and physical-device tests

**Unchecked items are not working features.** This is a scaffold, not a completed AI assistant.

## Quick start

Requirements: Windows 11 and Python 3.11.

In PowerShell, from this repository folder:

    Set-ExecutionPolicy -Scope Process Bypass
    .\setup.ps1
    .\launch.ps1

Open http://127.0.0.1:8765. The app initially binds to localhost only. Phone/LAN access stays disabled until authentication and network controls are implemented.

## Privacy and security

- SQLite data stays on this laptop in the data folder.
- Do not commit conversation memory, recordings, photos, model files, API keys, or other secrets.
- Raw audio recording is not implemented and must remain off by default.
- Camera capture is not implemented. A real hardware privacy switch must enforce capture-off, with an indicator when capture is active.
- This repository is currently public. Switch it to **Private** in GitHub Settings if you want the code restricted. Never commit credentials.

## Layout

- laptop/app.py: local dashboard and API
- setup.ps1: create venv and install dependencies
- launch.ps1: start the local app
- docs/: architecture, privacy, hardware, and test plan
- firmware/: reserved for ESP32-S3 firmware

Label features as **implemented**, **tested on laptop**, or **tested with physical glasses**. Hardware and offline claims require actual tests.
