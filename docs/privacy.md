# Privacy requirements

- Language-model inference, vision inference, OCR, transcription, and memory stay on the laptop.
- **Online neural speech is enabled by default on a fresh setup.** Text sent to be spoken is processed by the online speech service. The dashboard has a persistent toggle to disable online speech and use local Piper/Windows fallback instead.
- For a fully offline rehearsal, disable online speech in Settings, confirm the local voices work, cache all model assets, then disconnect the internet and test again.
- Dashboard camera control defaults off.
- A visual question, dashboard enable state, connected device, and physical switch are all required for capture.
- Firmware must check the physical switch immediately before capture and light the indicator while capturing.
- Dashboard state must mirror device-reported switch and indicator status; unverified is not the same as safe.
- Microphone audio is sent as short chunks over the trusted local network to the laptop for local transcription. Temporary WAV files are deleted after processing.
- Do not persist full voice transcripts by default. Save only a short summary when the user explicitly enables it.
- Keep local memory inspectable and deletable, stored on the laptop.
- Protect phone/LAN dashboard access with the generated PIN.
- Keep the device token private. The device protocol uses HTTP on the LAN, so use a trusted private network only.
- Never commit recordings, photos, SQLite databases, model files, passwords, tokens, or private transcripts.
- Test with internet disconnected and camera control disabled, then test the physical switch-off behavior.
- Get consent before capturing other people during tests.
