# Architecture

The Windows laptop is the local compute host. The candidate Seeed XIAO ESP32-S3 Sense handles camera and microphone input over the trusted local Wi-Fi network.

1. Device firmware: camera, PDM microphone, visible camera-activity indicator, physical privacy-switch input, Wi-Fi transport.
2. Laptop API: FastAPI service, local dashboard, PIN-protected optional LAN access, authenticated device endpoints.
3. Speech input: short WAV chunks from the device, cached multilingual faster-whisper transcription, configurable wake phrase, question collection until a pause.
4. Language model: Ollama local API, qwen2.5:1.5b primary and qwen2.5:0.5b fallback. Local model calls are restricted to loopback and unload after responses to limit RAM pressure.
5. Vision: a visual question triggers one-shot camera capture; local Moondream answers the question and Tesseract provides English/Telugu OCR.
6. Speech output: cached Piper neural English and Telugu voices; Windows SAPI/eSpeak fallback; short spoken answers while full answers remain text.
7. Memory: SQLite useful facts and opt-in short summaries. Full voice transcripts are not persisted by default.
8. Dashboard: laptop localhost mode by default; phone access through PIN-protected LAN mode on a trusted private network.

The laptop has an Intel Core i7-8650U and 8 GB RAM. Model response latency and memory pressure must be measured on the target laptop. The system uses local-only inference after initial downloads.

Current status: source integration is committed. Full setup runs local model, OCR, TTS, and firmware compile preflight checks. Actual camera/microphone behavior still requires the selected board to be purchased, wired, and tested.
