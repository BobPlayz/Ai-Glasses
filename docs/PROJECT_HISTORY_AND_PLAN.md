# Ai-Spects Project History, Current State, and Next Work

**Repository:** BobPlayz/Ai-Glasses  
**Snapshot date:** 12 October 2026

> **Truth rule:** Implemented in code, passed automated tests, tested on the laptop, and verified on assembled glasses are different states. Keep them separate.

## 1. Goal and constraints
Ai-Spects is a custom laptop-powered smart-glasses prototype. The laptop runs local AI; the candidate ESP32-S3 board handles wearable-side camera, microphone, status, and audio transport. Goals include offline-first operation, English and everyday Andhra Telugu, short spoken answers plus longer dashboard text, local memory, privacy-conscious camera/microphone control, and the dark/cyan reactor dashboard.

- Budget target: ₹3,000–₹6,000.
- The final glasses should not require a phone. The phone-camera bridge is only a temporary diagnostic option.
- Candidate controller: Seeed XIAO ESP32-S3 Sense. Exact revision and assembled wiring still need confirmation.
- Laptop last reported: Intel Core i7-8650U, 8 GB RAM, Windows 10 Pro. Performance must be measured.
- Exhibition target: 22 October 2026. Keep a laptop-only fallback if hardware cannot be validated safely.
- No AR display is part of the currently verified build.

## 2. Implemented work

### Repository and setup
- Windows setup/launch scripts, Python dependency list, local virtual-environment workflow, runtime data/model folders, and setup notes.
- Git ignore rules for databases, recordings, captures, models, local secrets, virtual environments, and generated PlatformIO output.
- FastAPI dashboard, device protocol, and GitHub Actions for Python checks and candidate firmware compilation.

### Local AI and memory
- Ollama local text inference with Qwen 2.5 1.5B primary model and a smaller fallback.
- SQLite useful-fact memory, search, delete/clear, opt-in conversation summaries, and recent dialogue context.
- Separate Gen Z style mode.
- Freshness-sensitive web research is separate from local inference and requires internet. It is not offline behavior.

### Speech and language
- Local Whisper transcription adapter.
- Piper offline speech path and Windows speech fallback.
- Optional online neural English/Telugu voices with a saved dashboard preference.
- Online speech sends the text being spoken to the selected online speech provider. Disable online voice for an offline-only demo.
- Wake-phrase configuration, English/Telugu visual-question phrase detection, streaming local text, phrase-level speech, and a bounded WAV queue for the paired device.

### Dashboard and device API
- Dark/cyan reactor dashboard with AI Core, Vision, and Settings.
- Controls for camera permission, device microphone permission, speech mode, wake phrase, memory, and style.
- Camera and device microphone permissions default off.
- Device routes use a pairing token; optional LAN dashboard mode uses a PIN.
- Device heartbeat/status and short-lived one-shot camera capture requests.
- Current XIAO firmware is not a continuous raw-video streamer.

### Vision
- Local Ollama image description and optional English/Telugu OCR.
- Image resize/compression, bounded retry, and actionable errors for empty replies, HTTP failures, timeouts, and invalid JSON.
- Safe per-attempt diagnostics for model, image byte count, response status, elapsed time, and whether answer content exists. Image contents/base64 should never be logged.
- Private-LAN camera URL validation and redirect blocking for the temporary phone-camera path and optional MJPEG helper.
- A direct Ollama generated-image test previously returned a response on the laptop. That proved direct inference for one test, not the full Ai-Spects route.

### Privacy and firmware
- Camera upload gates include active/unexpired request, dashboard permission, recent device status, camera state, physical-switch report, and indicator report.
- Server rechecks key privacy signals after upload.
- Firmware checks its physical switch immediately before frame transmission and caps frame size.
- Device audio uploads are blocked unless dashboard microphone permission is enabled.
- Candidate firmware covers camera capture, status, microphone chunks, and device protocol.
- Candidate I2S output uses GPIO4/5/6 for BCLK/WS/DATA, but physical amplifier/speaker operation is not confirmed.
- Microphone pin map corrected in docs: GPIO42 is PDM clock and GPIO41 is PDM data.

## 3. Security hardening added on 12 October 2026

- Added a request-body safety middleware with early Content-Length rejection and streamed byte counting; global cap is 22 MiB to allow bounded multipart uploads.
- Device microphone reads now stop at 2 MiB rather than buffering a body first.
- Added baseline security headers: no MIME sniffing, no framing, no referrer, browser camera/microphone/geolocation permissions disabled, and no-store caching.
- Local vision validates actual image format, limits pixel dimensions to 20 megapixels, rejects multi-frame images, and validates before OCR or inference.
- Dashboard PIN setup now uses cryptographic randomness and does not print the PIN to the setup console.
- CI now requests read-only repository content permission and runs a Python dependency vulnerability audit.
- Added regression tests for oversized microphone chunks, response headers, oversized image dimensions, and unsupported SVG content.
- Research basis: OWASP File Upload Cheat Sheet, FastAPI middleware guidance, and GitHub Actions secure-use guidance. These controls reduce attack surface but do not make this prototype safe for public internet exposure.

## 4. Recent reliability work and CI evidence

### Vision diagnostics
Commit: https://github.com/BobPlayz/Ai-Glasses/commit/e2871ae667af2081e67861b59df07cfb5a76552c

- Added tests for successful vision output, empty-first-response retry, empty responses twice, HTTP errors, timeouts, invalid JSON, and rejection of a non-local Ollama host.
- Added safe per-attempt diagnostics without logging image bytes.
- Corrected JPEG fixture bytes in API tests to use a real JPEG signature.

**CI found a production bug:** the valid camera-upload test returned HTTP 415 because the endpoint compared against an incorrectly escaped byte string. The follow-up changes the check to an explicit JPEG byte signature. Do not call this issue closed until current Python CI passes.

### Camera network hardening
Commit: https://github.com/BobPlayz/Ai-Glasses/commit/2e29e972729564e39359edd0cf35cb0a9b41d9d4

- Private-LAN camera fetch helpers do not follow redirects.
- Redirect regression test covers a camera URL attempting to redirect elsewhere.
- Candidate firmware compile check passed on that earlier commit.

### CI state at the time of writing
- Firmware compile passed for e2871ae.
- Python tests failed for e2871ae because the valid camera-upload test received HTTP 415.
- Earlier commit 2e29e97 had a passing Python test workflow.
- Check the latest workflow after the production JPEG fix. Do not claim a green suite until GitHub reports success.

## 5. Current status by evidence

### Implemented in repository
Local text model adapter, memory, dashboard, speech adapters, vision adapter, API privacy gates, device token/PIN checks, candidate firmware, and automated checks.

### Demonstrated by earlier laptop evidence
Ollama listed a local vision model and accepted one generated image through its direct API. Some earlier dashboard/phone-camera attempts returned HTTP 503 or an empty description, prompting retry and diagnostics work. Local setup and dependency installation were started, but a complete final rehearsal is not confirmed.

### Not yet demonstrated end-to-end
- Current commit full Python CI passing.
- A real generated image returning a useful answer through the Ai-Spects dashboard after the latest fix.
- Reliable phone snapshot-to-answer flow.
- Full offline operation with all models and voices cached.
- Real board flashing, heartbeat/pairing, camera switch, visible indicator, microphone quality/revocation, and actual speaker playback.
- Safe battery/charging setup, final mounting, and complete wearable operation.

## 6. Security rules
Read [SECURITY.md](SECURITY.md) before enabling LAN mode or handling camera/audio data.

1. Keep the dashboard on localhost by default.
2. Do not port-forward or publicly expose it.
3. LAN mode is only for trusted private Wi-Fi and requires a unique PIN.
4. Never commit dashboard PIN, device token, Wi-Fi passwords, recordings, captured frames, memory databases, or model files.
5. Do not log image/audio payloads, PINs, or pairing tokens.
6. Keep camera and microphone permissions off until explicitly needed.
7. A firmware-reported switch is not an electrical camera power disconnect.
8. Use private-LAN camera URLs, enforce size limits, and do not follow redirects.
9. Do not connect a battery/charger until wiring and ratings are reviewed by a qualified adult/technician.
10. Green CI means code checks passed, not that hardware is safe or functional.

## 7. Next actions in order
1. Confirm Python tests, firmware compile, and dependency audit are green; inspect full logs if any check fails.
2. Exercise request-size limits, JPEG validation, pixel-bomb rejection, security headers, tokens, disabled camera/mic, stale heartbeat, expired request, redirects, and revocation.
3. Test vision through Ai-Spects itself using a generated PNG, then a real image and temporary phone route if needed.
4. Finish laptop setup and confirm the documented command and required assets work.
5. Rehearse offline: test text, memory, English/Telugu speech, transcription, OCR, and vision with internet disconnected.
6. Confirm parts and board revision: pinout, amplifier labels, speaker impedance/power, cable type, and power module.
7. Bench-test with supervision: USB first; check continuity, polarity, insulation, switch/indicator, camera, mic, and speaker.
8. Run exhibition rehearsal and record real latency, fallback behavior, privacy demonstration, and limitations.
9. Review secret exposure risk and confirm runtime files remain ignored by Git.
10. After core stability, consider BobAI integration and any display as separate future work.

## 8. Exhibition acceptance checklist
- [ ] Documented setup launches the dashboard.
- [ ] Current Python tests and firmware build checks pass.
- [ ] Text AI answers locally with internet disconnected.
- [ ] Memory save/read/delete/clear works.
- [ ] English and Telugu speech are tested offline.
- [ ] Transcription works with intended microphone input.
- [ ] A generated image works through the application vision route.
- [ ] Camera/microphone default-off behavior and revocation are tested.
- [ ] LAN mode is PIN-protected and remains on trusted Wi-Fi.
- [ ] Physical switch and indicator are observed on the actual board.
- [ ] Glasses speaker plays real assistant audio, or laptop audio is clearly used as fallback.
- [ ] Power/battery wiring is checked before portable use.
- [ ] Offline rehearsal is repeatable.
- [ ] Presentation separates tested behavior from planned features.

## 9. Documentation map
- [roadmap.md](../roadmap.md): short ten-phase execution checklist.
- [SECURITY.md](SECURITY.md): security boundaries and privacy test checklist.
- [AI_SPECTS_INTEGRATION_STATUS.md](AI_SPECTS_INTEGRATION_STATUS.md): hardware/software integration status.
- [FINAL_SOFTWARE_AUDIT.md](FINAL_SOFTWARE_AUDIT.md): software audit notes and test instructions.
- [hardware.md](hardware.md): candidate hardware and wiring notes.

Update this file when a meaningful feature lands, CI changes, or a real-device test adds evidence. Keep code, automated test, laptop, and physical-device status separate.
