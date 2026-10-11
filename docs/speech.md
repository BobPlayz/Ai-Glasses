# Offline speech

## Input
The candidate ESP32-S3 firmware samples the onboard PDM microphone at 16 kHz, mono, 16-bit and sends short WAV chunks to the laptop over the private LAN. The laptop uses a cached multilingual faster-whisper base model with CPU int8 inference. Temporary WAV files are deleted immediately after transcription.

The wake phrase is configurable in the dashboard and stored locally. The default phrase "hey glasses" is only a placeholder until the user sets their chosen phrase. After detection, the system collects transcript chunks until a pause, then processes the question. Visual phrases trigger one-shot camera capture only when dashboard permission and the physical switch are enabled.

## Output
Piper neural voice assets are cached locally:
- English: en_US-lessac-medium
- Telugu: te_IN-maya-medium

The assistant speaks a short answer and exposes the full answer in dashboard text. Windows SAPI and eSpeak NG are fallback engines. Voice quality, Telugu pronunciation, and end-to-end latency are checked during setup and must be rehearsed on the target machine.

No cloud speech API is used.
