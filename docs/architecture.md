# Architecture

The Windows laptop is the compute host. The glasses board handles sensors and transports frames/audio over the local network. The core assistant must not require cloud APIs.

1. Device firmware: camera, microphone, visible activity indicator, physical privacy input, Wi-Fi transport.
2. Laptop API: FastAPI service, local dashboard, authenticated device endpoints.
3. Speech: local wake-word detector, multilingual English/Telugu ASR, local TTS.
4. Language model: small quantized model chosen after CPU/RAM benchmarking.
5. Vision: local image question answering and OCR; capture only after an explicit visual question.
6. Memory: SQLite for useful facts and concise conversation summaries.
7. Dashboard: laptop first; phone access only after authentication and LAN tests.

The current app binds to 127.0.0.1 only. Do not bind to 0.0.0.0 until authentication, device pairing, and firewall behavior are implemented and tested. Local Wi-Fi is not automatically trusted.

The laptop has an Intel Core i7-8650U and 8 GB RAM. Start with small quantized models and measure latency/RAM. Avoid loading speech, vision, and LLM models concurrently if memory pressure is high.

Current state: dashboard/API and SQLite memory scaffold only. No LLM, ASR, TTS, camera, microphone, firmware, or device transport is integrated yet.
