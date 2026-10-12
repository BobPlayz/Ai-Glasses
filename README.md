# AI Glasses

A local-first smart-glasses prototype for a school exhibition. The Windows laptop is the AI host; the candidate physical controller is the Seeed XIAO ESP32-S3 Sense. The board has not been confirmed as purchased or physically tested.

## Included in this repository

- Existing dark/cyan reactor dashboard amplified with a perspective-grid background and three primary controls: AI Core, Vision, Settings
- Detailed device connections, microphone, voice, and memory controls tucked into Settings
- Local Ollama text assistant with primary and fallback models
- SQLite useful-fact memory and opt-in short conversation summaries
- Offline multilingual Whisper transcription adapter and cached-model setup
- Switchable Microsoft neural online TTS for natural English/Telugu speech, with cached offline Piper fallback
- Local Tesseract OCR using English and Telugu language data
- Local vision adapter for an explicitly supplied image, combined with OCR results
- Live glasses vision using sequential privacy-gated JPEG snapshots and local vision/OCR inference; bounded private-LAN MJPEG helper for compatible sources
- Dashboard camera enable/disable control, default off
- Explicit device microphone enable/disable control, default off, with server-side upload rejection until opted in
- Paired-device API with token authentication, camera command queue, one-shot and sequential live JPEG capture, and bounded local Piper WAV delivery to the glasses speaker
- Candidate ESP32-S3 camera, privacy-switch, indicator, and microphone firmware
- Hardware integration status and remaining work documented in `docs/AI_SPECTS_INTEGRATION_STATUS.md`
- Configurable wake phrase and local audio chunk processing
- Local-only mode and optional PIN-protected LAN dashboard mode
- Unit tests and GitHub Actions checks

## Requirements

- Windows 10 or 11 (64-bit; Python 3.11 is required)
- Python 3.11
- Internet for first-time dependencies and model caching
- Ollama
- For physical glasses: compatible ESP32-S3 camera/microphone board, USB cable, switch, indicator LED and resistor, safe mounting, and wiring verified for the exact board revision
- Tesseract OCR engine, installed by setup

## Setup

From PowerShell in the repository directory:

    Set-ExecutionPolicy -Scope Process Bypass
    .\setup.ps1

Setup creates the Python environment, installs dependencies, creates a private dashboard PIN and device pairing token, downloads and verifies the local speech/OCR assets, pulls the Ollama models, compiles the candidate firmware, and runs the software checks. The first run needs internet and can take a while because the model files are large. Keep the PIN and token private. If Ollama was installed during setup but is not available in the current shell, reopen PowerShell and rerun setup to finish model caching.

For an existing setup, install and verify the offline male English and Telugu voices without repeating all model downloads:

    powershell -ExecutionPolicy Bypass -File .\scripts\install_british_voice.ps1

### Speech voices

In Settings → Voice & wake phrase, enable **Natural online voice** for neural speech through `edge-tts`. It uses a natural US English neural voice and an Indian Telugu neural voice, and requires internet access. Text sent for speech is processed by the online speech service. This community integration is not an official Microsoft Speech SDK integration and may occasionally stop working if the upstream service changes.

Turn it off to use cached Piper neural voices locally: Alan for British English and Venkatesh for Telugu. Offline speech needs no API key or cloud service. The separate **Gen Z style** toggle controls wording, not the audio voice. Online speech is used for browser playback and paired-device audio; if online synthesis fails, the existing offline voice remains available.

For laptop-only mode:

    .\launch.ps1

Open http://127.0.0.1:8765.

### Use an Android phone as a temporary camera

1. Install **IP Webcam** from the Play Store on the OnePlus phone.
2. Connect the phone and laptop to the same trusted Wi-Fi network.
3. Open IP Webcam and tap **Start server**. Keep the app open.
4. The app shows a phone URL such as `http://192.168.1.50:8080`. In the laptop dashboard, open **Android phone camera** and enter `http://192.168.1.50:8080/shot.jpg` using your actual phone IP.
5. Press **Test connection**, then enter a question in the vision question field and press **Capture & analyze**.

This bridge requests one still frame per button press, not continuous video. The laptop fetches the snapshot over the local network and sends it to the existing local vision/OCR pipeline. It accepts only private-LAN IP addresses and JPEG/PNG still-image URLs. Keep both devices on a trusted network, and stop the IP Webcam server or press Disconnect when finished. This phone-camera route is separate from the glasses camera privacy switch.

For phone access on a trusted private Wi-Fi network:

    .\launch-lan.ps1

Find the laptop IPv4 address using ipconfig, then open http://LAPTOP-IP:8765 on the phone. Enter the generated dashboard PIN. Do not use public/shared Wi-Fi; this prototype's device protocol uses HTTP on the trusted LAN.

## Models

- Text primary: qwen2.5:1.5b
- Text fallback: qwen2.5:0.5b
- Speech: faster-whisper base multilingual model
- Vision candidate: moondream:1.8b
- OCR: local Tesseract with eng+tel data
- TTS: Piper en_GB-alan-medium British English and te_IN-venkatesh-medium Telugu voices

These are configuration candidates. Actual model latency, memory pressure, Telugu recognition quality, and voice availability must be verified on the target laptop. The app never downloads models while answering a question. On an 8 GB laptop, close memory-heavy apps during first model loads; local vision inference may be slower than text chat.

## Privacy defaults

- Dashboard camera control starts disabled.
- Capture requires dashboard camera permission, a connected device, and the physical switch enabled. Live vision repeats single-frame capture and local inference until stopped.
- Firmware turns on the capture indicator while obtaining a frame and stops the camera driver when the dashboard control or physical switch disables it.
- Device microphone is disabled by default. Audio capture/upload starts only after explicit dashboard opt-in; the laptop server rejects device audio while disabled, and firmware stops reading/uploading when the permission is revoked. When enabled, short audio chunks are sent to this laptop for local processing. Temporary WAV files are deleted after processing; recognized transcripts are not saved unless the user explicitly asks to save a summary.
- Memory is local and can be inspected or cleared.
- The dashboard is localhost-only by default. LAN mode requires the generated PIN.
- Device credentials, PINs, local memory, recordings, and model files are excluded from Git.

The XIAO camera path uses sequential privacy-gated snapshots, not a high-frame-rate raw video stream. When cached Piper voices are available, assistant responses can be queued to the MAX98357 through I2S; the laptop output remains the fallback. The selected 2-inch speaker's impedance/power rating and the 5 V power module wiring must be verified before use. **BOM safety gap:** the locked list does not explicitly include an external camera indicator LED. Do not use the camera on a wearable until a clearly visible indicator is confirmed or added. A firmware switch is not an electrical camera power disconnect. Have an experienced adult/technician verify wiring and the power path; do not improvise battery or charging circuits.

## Dashboard controls

- **AI Core** pauses dashboard interaction and revokes camera/microphone permissions. Resuming does not silently re-enable them.
- **Vision** opens image upload, one-shot capture, or sequential live vision.
- **Settings** contains connection status, camera/microphone permissions, voice, and local memory controls.

Live glasses-speaker playback uses cached local Piper WAV audio, requires the paired firmware and a compatible MAX98357/speaker connection, and is not physically verified until the hardware is assembled.

## Tests and status

Run Python checks with:

    .\.venv\Scripts\python.exe -m compileall laptop tests
    .\.venv\Scripts\python.exe -m unittest discover -s tests -v

The API privacy tests cover default-off camera/microphone permissions, microphone upload rejection, dashboard opt-in/revocation, and device-token enforcement.

Firmware compile check:

    pio run -d firmware/xiao-esp32s3-sense

Committed code and CI checks do not certify that the selected board works physically. Do not claim the full offline demo is verified until it has been rehearsed with the internet disconnected and the exact hardware.
