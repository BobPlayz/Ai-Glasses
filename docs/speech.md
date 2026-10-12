# Speech system

## Input
The candidate ESP32-S3 firmware samples the onboard PDM microphone at 16 kHz, mono, 16-bit and sends short WAV chunks to the laptop over the private LAN. The laptop uses a cached multilingual faster-whisper base model with CPU int8 inference. Temporary WAV files are deleted immediately after transcription.

The wake phrase is configurable in the dashboard and stored locally. The default phrase "hey glasses" is only a placeholder until the user sets their chosen phrase. After detection, the system collects transcript chunks until a pause, then processes the question. Visual phrases trigger one-shot camera capture only when dashboard permission and the physical switch are enabled.

## Output
- **Default on a fresh setup:** online Microsoft neural TTS via `edge-tts`, using `en-US-AvaNeural` for English and `te-IN-ShrutiNeural` for Telugu.
- **Fallback:** cached local Piper voices, with Windows speech as an English fallback when Piper is unavailable.
- The dashboard's online-voice toggle is separate from the Gen Z wording toggle and persists on the laptop.
- Online speech requires internet access and sends the text being spoken to the speech provider. Local language-model inference remains on the laptop.
- For offline use, switch online speech off and verify the installed Piper voices before disconnecting the internet.
- The assistant exposes the full answer as dashboard text and can queue bounded WAV audio for the paired device. Real device-speaker playback still needs physical integration testing.

Voice quality, Telugu pronunciation, and end-to-end latency must be rehearsed on the target machine.
