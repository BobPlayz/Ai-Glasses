# Offline speech plan

The repository includes an audio-file transcription adapter based on faster-whisper and a best-effort local eSpeak NG output adapter.

- Speech transcription defaults to the multilingual Whisper base model with CPU int8 inference.
- The transcription adapter uses local-files-only mode; it does not download models at runtime.
- The project still needs a setup/cache step for the model, an audio stream from the selected glasses board, wake-word detection, and end-to-end latency tests.
- eSpeak NG is a functional offline fallback, not a promise of natural Telugu. Test installed Telugu voice support on the actual laptop. If quality is poor, display the text answer rather than misrepresenting voice quality.
- No always-listening loop or hardware microphone integration is claimed yet.
