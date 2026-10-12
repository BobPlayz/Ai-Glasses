# Ai Spects Dashboard Controls Specification

## Purpose

This document is the source of truth for what the Ai Spects laptop dashboard should show and control. Build from the existing repository and current main branch. Do not switch to Replit or redesign the architecture.

## Product goal

Ai Spects is a finished wearable smart-glasses device whose camera, microphone, speaker/audio output, battery, and physical privacy controls are on the glasses. The laptop runs the heavy AI workloads. The glasses connect to the laptop over trusted local Wi-Fi.

The user should be able to wear the glasses and interact with the AI through the glasses' own microphone and speaker. The laptop may stay nearby or in a bag, but it must be on and connected for the current architecture to provide AI features.

## System responsibilities

### Glasses hardware
- XIAO ESP32-S3 Sense with its camera and PDM microphone expansion board.
- Capture images and microphone audio and send data to the laptop over local Wi-Fi.
- Play AI responses through a compatible speaker/audio module physically attached to the glasses. This output hardware still needs to be selected, wired, and implemented; do not pretend it already works.
- Battery and charging hardware suitable for the final wearable build. Do not assume battery telemetry exists until firmware actually reports it.
- Physical privacy control and visible camera-activity indicator. Current firmware's GPIO 2 privacy input is software-controlled and is NOT an electrical power disconnect. Do not label it as hardware-enforced isolation.
- Compact, removable, wearable mounting.

### Laptop
- Runs the local AI runtime and orchestration.
- Runs local vision/image understanding, OCR, speech recognition, text-to-speech, memory, and other capabilities that are actually configured in the repository.
- Hosts the dashboard and communicates with the glasses over the trusted local network.
- Laptop speakers are for development/testing only, not the intended finished-product audio path.

## Dashboard layout

### 1. Main status header
Show:
- Ai Spects connection state: Connected / Disconnected / Reconnecting.
- Last successful device heartbeat or message time.
- Laptop AI runtime state.
- Local network/API state.
- Clear error details and a retry/reconnect action when appropriate.

Only show live states based on actual device/runtime responses. Never hardcode Connected, battery percentage, camera status, or model readiness.

### 2. Glasses status card
Show the information the firmware actually reports:
- Device identity/name.
- Wi-Fi connection and signal information, if reported.
- Camera availability.
- Microphone availability.
- Privacy input state.
- Camera-activity indicator state, if reported.
- Speaker/audio output readiness, only after the glasses audio hardware and firmware are implemented.
- Battery percentage/charging state, only after hardware sensing and firmware telemetry exist.

For unavailable telemetry, display “Not available” or “Not implemented yet”, not a guessed value.

### 3. Core controls
Provide clear controls for:
- Connect / Disconnect / Reconnect glasses.
- Start / Stop camera capture.
- Enable / Disable microphone capture.
- Privacy mode, reflecting the physical privacy input and software permission.
- Ask AI / push-to-talk interaction.
- Stop current speech playback.
- Mute/unmute glasses audio once wearable audio is implemented.
- Emergency stop that halts capture and pending audio tasks.

Controls must have real callbacks and report success/failure from the backend. Do not add decorative controls that do nothing.

Privacy rules:
- Default to camera and microphone off until the user explicitly enables them.
- Show a persistent visible privacy state.
- When privacy is enabled, stop capture and discard queued capture work.
- Never imply the GPIO 2 software input electrically disconnects camera/mic power.
- Keep a clear visible camera-active indicator when capture is active.

### 4. Live interaction panel
Show:
- Push-to-talk state (Idle / Listening / Processing / Speaking / Error).
- A short transcript of the user's latest request when speech recognition is enabled.
- The AI response text.
- Current speech playback state.
- A cancel/stop action.

Do not save or show raw audio/video history by default. Make any logging or retention explicit and configurable.

### 5. AI services panel
Show actual readiness and errors for the services configured by the project, such as:
- Ollama and selected local model.
- Vision model.
- Speech recognition.
- OCR with installed languages.
- Text-to-speech voice.
- Memory service, if enabled.

Each service needs a real health check, state, and useful error message. Do not display a service as ready just because a model name is configured.

### 6. Activity and diagnostics
Show a small, privacy-conscious event log:
- Device connected/disconnected.
- Capture started/stopped.
- Privacy toggled.
- AI request started/completed/failed.
- Speech playback started/stopped/failed.
- Service errors.

Do not log secrets, Wi-Fi passwords, authentication tokens, or raw camera/microphone data. Let the user clear the log.

### 7. Settings
Include:
- Device endpoint and connection settings.
- Authentication/token setup without revealing stored secrets.
- Model selection from models that are actually installed.
- Speech recognition and TTS settings.
- OCR language settings.
- Privacy defaults and logging/retention controls.
- Audio output selection once glasses audio is implemented.
- Diagnostics/export for troubleshooting, excluding secrets and private media.

## Visual and interaction requirements
- Clean, compact, readable dashboard with clear status colors and labels.
- Mobile-friendly layout so the dashboard can be checked from a phone on the same network, if the existing server supports it.
- Every interactive element must work and show loading, success, and failure states.
- Use explicit labels; do not rely on color alone.
- Keep errors actionable and avoid overwhelming the main screen.
- Do not invent hardware or capabilities that have not been built.

## Implementation truth: planned versus working

The repository already contains a laptop-hosted AI architecture and XIAO ESP32-S3 Sense firmware direction. The camera/microphone board is the intended glasses peripheral. The final glasses speaker/audio path, battery integration/telemetry, physical privacy protection, and wearable mounting still require hardware selection and implementation unless the codebase proves otherwise.

The dashboard must distinguish:
- Working: verified by real runtime/device responses.
- Planned: intended but not yet implemented.
- Unavailable: required service/device is offline or cannot be checked.

## Acceptance checklist
- [ ] Dashboard reflects actual device connection state.
- [ ] Capture controls call real backend/device operations.
- [ ] Privacy state is always visible and capture stops when privacy is enabled.
- [ ] AI/service cards use real health checks.
- [ ] Push-to-talk flow visibly moves through Listening, Processing, Speaking, and Error as applicable.
- [ ] Stop/cancel interrupts active work.
- [ ] No fake battery, signal, speaker, or model statuses.
- [ ] No secrets or raw media are written to logs by default.
- [ ] Dashboard does not depend on Replit.
- [ ] Documentation and implementation stay aligned with the main branch.
