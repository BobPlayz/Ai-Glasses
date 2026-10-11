# AI Glasses: 10-Phase Roadmap

**Project:** BobPlayz/Ai-Glasses  
**Purpose:** A local-first smart-glasses prototype hosted by a Windows laptop, with an Android phone available as a temporary camera input.  
**Status date:** 11 October 2026  
**Roadmap rule:** Distinguish code that exists from functionality verified on the actual laptop or hardware. A successful commit or CI run is not proof of a complete physical demo.

## Executive status

The software foundation, local AI adapters, dashboard, privacy controls, candidate ESP32-S3 firmware, setup scripts, and CI checks are in the repository. This conversation also confirmed that Ollama is reachable and that `moondream:1.8b` can return a result for a real test image sent directly to its API. The Android phone camera integration has been implemented, but its end-to-end flow through the Ai-Glasses dashboard is **not yet verified**: earlier attempts returned HTTP 503, and a later attempt reported that the local vision model returned no description.

The immediate priority is to finish diagnosis and make the phone-image-to-local-vision path reliable before adding more features or attempting hardware integration.

---

## Phase 1: Define the architecture and project boundaries

**Goal:** Keep the prototype local-first, understandable, and safe to demonstrate.

### Accomplished
- Defined the Windows laptop as the local AI host.
- Selected the Seeed XIAO ESP32-S3 Sense as a candidate physical controller, without claiming that a board has been purchased or physically tested.
- Established the local dashboard as the primary control surface, with localhost mode as the default and optional PIN-protected LAN mode.
- Organized the project around local services rather than requiring cloud inference for normal operation.
- Documented the boundary between implemented software and hardware that still needs physical verification.

### Current constraints
- The target laptop has 8 GB RAM and Intel integrated graphics; local CPU inference can be slow.
- Python 3.11 is required by the project setup. The user's machine has Python 3.14 installed as well, so the project-local virtual environment must be checked to ensure it uses 3.11.
- Model latency, Telugu quality, voice quality, and offline behavior must be verified on the target machine.

### Next actions
- Keep the scope focused on a reliable demonstration instead of adding new features during debugging.
- Record the exact laptop, Python environment, Ollama version, and model versions used for final testing.
- Keep the README and this roadmap honest about what is software-complete versus physically verified.

**Exit criteria:** The intended architecture and known limitations are documented, and the team can explain which services run locally.

---

## Phase 2: Windows setup, dependencies, and repeatable launch

**Goal:** Make setup and launch reproducible from a clean checkout.

### Accomplished
- Added `setup.ps1` and `launch.ps1` workflows.
- Added Python 3.11 environment validation and recreation of the project-local `.venv` when it is missing or uses the wrong Python version.
- Setup handles dependencies and local assets for speech, OCR, Ollama models, and candidate firmware.
- Added a separate LAN launch script for use on a trusted private network.
- Documented the normal local URL: `http://127.0.0.1:8765`.
- Added setup and troubleshooting instructions to the repository documentation.

### Known setup procedure
From the repository root in PowerShell:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\setup.ps1
.\launch.ps1
```

### Next actions
- Confirm the active environment with `.\.venv\Scripts\python.exe --version` and ensure it reports Python 3.11.
- Re-run setup only when needed; avoid repeatedly redownloading large model assets during feature debugging.
- Verify a fresh setup on a clean checkout when time permits.

**Exit criteria:** A clean checkout can set up and launch the local dashboard without manually repairing the environment.

---

## Phase 3: Local language AI, memory, speech, and OCR

**Goal:** Provide useful offline interactions without sending user data to a cloud AI service.

### Accomplished
- Integrated local Ollama text models:
  - Primary: `qwen2.5:1.5b`
  - Fallback: `qwen2.5:0.5b`
- Added local SQLite useful-fact memory and opt-in conversation summaries.
- Added an offline multilingual Whisper transcription adapter with a cached model.
- Added cached Piper neural speech voices for British English and Telugu, with a Windows speech fallback for English.
- Added local Tesseract OCR for English and Telugu when the required language data is available.
- Added a local vision adapter that combines an image question with optional OCR output.
- Documented that local answers should not download models during a question.

### Next actions
- Smoke-test text, memory save/read/clear, English speech, Telugu speech, and transcription separately.
- Verify that all model and voice assets are cached before the offline rehearsal.
- Record observed latency and quality on the actual laptop rather than relying on model specifications.

**Exit criteria:** Each local AI capability works independently with cached assets, and its failures are reported clearly.

---

## Phase 4: Dashboard, connections, and controls

**Goal:** Make system state and user-controlled connections visible in one place.

### Accomplished
- Added the dark/cyan dashboard UI.
- Added a Connections hub with:
  - Glasses Wi-Fi/heartbeat status.
  - Glasses camera permission control.
  - Glasses microphone permission control.
  - Laptop microphone connect/disconnect controls.
  - Local speaker/voice output test.
- Added a dashboard camera enable/disable control that defaults off.
- Added device microphone permission control that defaults off.
- Documented that USB currently serves power/programming purposes and is not represented as a live-data connection.

### Next actions
- Test every dashboard control and verify that its visible state matches backend behavior.
- Ensure errors are displayed to the user instead of being reduced to vague generic messages.
- Check that the dashboard remains usable after a service failure and can retry without a full reinstall.

**Exit criteria:** The dashboard accurately reflects service status and controls supported actions without pretending unimplemented connections work.

---

## Phase 5: Privacy, local network restrictions, and device API

**Goal:** Make camera and microphone use explicit, revocable, and bounded.

### Accomplished
- Dashboard camera capture defaults off.
- Device microphone capture/upload defaults off.
- Server rejects device-audio uploads until permission is explicitly enabled.
- Firmware logic checks permission and stops reading/uploading audio when permission is revoked.
- Camera flow is designed around explicit capture, an indicator, and a physical switch.
- Device API uses a pairing token.
- Dashboard LAN mode uses a generated PIN and is intended only for a trusted private network.
- Added API privacy and device-protocol tests.
- Excluded device credentials, PINs, memory, recordings, and model files from Git.

### Important limitation
A firmware-controlled switch is not an electrical power disconnect for the camera. Physical wiring, indicators, board pin assignments, and safe power must be checked on the exact board before assembly.

### Next actions
- Re-run privacy tests after any changes to camera, audio, or device endpoints.
- Test permission revocation during an in-progress action, not only before starting one.
- Review LAN behavior on a trusted network and never expose the prototype directly to the public internet.

**Exit criteria:** Default-off behavior, permission enforcement, revocation, and device authentication pass automated and manual checks.

---

## Phase 6: Candidate ESP32-S3 firmware and CI

**Goal:** Keep candidate firmware buildable and catch software regressions automatically.

### Accomplished
- Added candidate firmware for the XIAO ESP32-S3 Sense, covering camera capture, privacy switch/indicator concepts, microphone handling, device heartbeat, and the device protocol.
- Added a PlatformIO firmware build check.
- Added GitHub Actions checks for Python compilation/unit tests and firmware compilation.
- Updated workflow action versions in the repository.
- Documented that a successful firmware build does not prove the board works physically.

### Next actions
- Check the latest GitHub Actions runs for the current default-branch commit.
- Confirm the exact board revision and verify camera/microphone pin mapping against official board documentation.
- Keep private Wi-Fi credentials and device tokens out of committed firmware secrets.
- Only upload to hardware after the wiring and power arrangement have been reviewed by a qualified adult/technician.

**Exit criteria:** CI passes on the current commit, and firmware is ready for a controlled hardware test without secrets committed.

---

## Phase 7: Android phone camera bridge

**Goal:** Use the Android phone as a temporary camera while physical glasses hardware is not yet verified.

### Accomplished
- Added a dashboard panel called **Android phone camera**.
- Added a phone-camera analysis endpoint: `POST /api/phone-camera/analyze`.
- Added support for a single snapshot request from an Android IP Webcam URL, typically ending in `/shot.jpg`.
- Added a Test connection action, Capture & analyze action, and Disconnect control.
- Added validation for private LAN IP addresses, HTTP-only snapshot URLs, allowed image path suffixes, JPEG/PNG content signatures, request timeout, and an 8 MB image limit.
- Documented same-Wi-Fi setup and the fact that this is a one-shot image flow, not continuous video.
- Fixed a JPEG/PNG signature-validation bug in a prior commit.
- Added image preprocessing in the latest fetched vision code: resize to a maximum 1280 × 1280 and encode as JPEG quality 85 before vision inference. OCR is attempted on the original image.

### Known issue
The end-to-end phone-camera analysis path has not yet been proven reliable. Earlier dashboard calls returned HTTP 503. A subsequent error said: `The local vision model returned no description. Please try the image again.`

### Next actions
1. Update the local checkout to the latest default branch and restart the dashboard.
2. Test the same small generated image that already succeeded with a direct Ollama API call, this time through the Ai-Glasses local vision function or dashboard upload path.
3. If it fails, capture the full response body/detail and server traceback. Do not infer the cause from the access log alone.
4. Test the phone snapshot endpoint separately in a laptop browser and verify it returns an actual JPEG/PNG image.
5. Test with a modest-resolution phone image after the small-image test passes.
6. Add automated tests around image preprocessing and Ollama responses, including empty model responses and HTTP errors.
7. Confirm that the dashboard clearly shows when OCR-only fallback is used versus a genuine vision answer.

**Exit criteria:** A snapshot from the phone reaches the local pipeline and produces a useful answer, with errors shown accurately and no cloud service involved.

---

## Phase 8: Local vision reliability and performance

**Goal:** Make image questions reliable on an 8 GB CPU-only laptop.

### Accomplished
- Confirmed through a direct command-line API test that Ollama's `/api/tags` endpoint lists `moondream:1.8b` with vision capability.
- Confirmed that the installed models include `moondream:1.8b`, `qwen2.5:0.5b`, and `qwen2.5:1.5b`.
- Successfully sent a generated 320 × 200 PNG image with the words **RED APPLE** directly to Ollama's `/api/chat` endpoint.
- Ollama returned the content `!!!RED APPLE!!!` with `done: true`, proving that at least one real image inference request succeeded.
- The successful direct image request reported approximately 27.6 seconds total duration, including approximately 5.8 seconds of model load time.
- Changed the vision request's `keep_alive` from `0` to `5m`.
- Increased the main and retry request timeouts from 60 to 180 seconds.
- Improved the generic network/timeout error so it includes the exception type and message.
- Added image downscaling/compression before sending the image to Moondream.

### What is not yet proven
- The direct test proves Ollama can process at least one image. It does not prove that Ai-Glasses' own function, dashboard, or phone-camera flow works.
- The latest observed Ai-Glasses error is an empty model description after its retry, rather than a successful answer.
- `ollama ps` previously showed the model in `Stopping...`; that is consistent with model unloading but does not by itself explain the empty response.

### Next actions
- Reproduce the generated-image test through the exact Ai-Glasses function and record the returned model, answer, OCR text, and exceptions.
- Inspect the full Ollama response JSON for empty answers, including any error field or unexpected response structure.
- Add bounded retries only for transient/empty responses and log safe diagnostic details to the local server console.
- Verify that the configured model name is exactly `moondream:1.8b` and the local Ollama host is `http://127.0.0.1:11434`.
- Compare direct Ollama latency with Ai-Glasses latency using the same image and prompt.
- Keep image size bounded and avoid unnecessary OCR work when no OCR engine is installed.
- Do not claim the vision pipeline is fixed until an image request through the application returns a useful answer.

**Exit criteria:** The same image succeeds through both direct Ollama and Ai-Glasses, and empty responses/timeouts produce actionable diagnostics.

---

## Phase 9: Full software regression and offline rehearsal

**Goal:** Verify that the whole laptop-only demo is repeatable before adding physical hardware.

### Accomplished
- Documented the main software checks in `README.md` and `docs/FINAL_SOFTWARE_AUDIT.md`.
- Added automated tests for API privacy and device protocol behavior.
- Documented a local-only launch path and an optional PIN-protected LAN path.
- Identified the need to rehearse with the internet disconnected after all models and assets have been cached.

### Next actions
Run from the repository root after setup:

```powershell
.\.venv\Scripts\python.exe --version
.\.venv\Scripts\python.exe -m compileall laptop tests
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
pio run -d firmware/xiao-esp32s3-sense
```

Then manually verify:
- [ ] Dashboard launches at `http://127.0.0.1:8765`.
- [ ] Local text question returns an answer.
- [ ] Memory can be saved, inspected, and cleared.
- [ ] English and Telugu speech are tested.
- [ ] Offline transcription is tested with the intended microphone input.
- [ ] Small generated image succeeds through Ai-Glasses, not only direct Ollama.
- [ ] Android phone snapshot succeeds over the same trusted Wi-Fi.
- [ ] Camera and microphone permissions start disabled.
- [ ] Device microphone uploads are rejected while disabled.
- [ ] LAN mode is PIN-protected and not exposed to public networks.
- [ ] The demo is rehearsed with internet disconnected.
- [ ] Latency, voice quality, and Telugu recognition are recorded honestly.

**Exit criteria:** Automated checks pass on the current commit and the laptop-only demo completes without internet after initial caching.

---

## Phase 10: Physical hardware integration and demo readiness

**Goal:** Integrate the candidate glasses board only after the software demo is stable.

### Accomplished
- Identified the candidate XIAO ESP32-S3 Sense controller and the need for a camera, microphone, physical switch, indicator LED/resistor, safe mounting, and verified wiring.
- Documented hardware setup as pending rather than claiming physical validation.
- Documented that board-specific pin mapping, power, charging, and camera privacy wiring must be checked before assembly.

### Next actions
1. Confirm the exact board revision and obtain its official pinout.
2. Prepare firmware secrets locally from the example file; never commit actual Wi-Fi credentials or device tokens.
3. Have a qualified adult/technician review switch, indicator, power, battery, and charging wiring before powering the assembly.
4. Compile and upload the firmware to the actual board.
5. Verify the device heartbeat and pairing.
6. Test the physical camera switch and indicator before enabling capture.
7. Test microphone permission revocation and ensure audio capture stops.
8. Verify one-shot image capture and local analysis.
9. Repeat the privacy tests and offline rehearsal with hardware connected.
10. Record what worked, measured latency, and any limitations for the exhibition demo.

**Exit criteria:** Physical hardware behavior is tested on the exact board and safe wiring; the final demo works offline and privacy controls are demonstrated.

---

## Immediate priority queue

Do these in order. Avoid starting a new feature until item 1 is resolved.

1. **Fix the Ai-Glasses empty vision response.** The direct Ollama image test works, but the app's local vision path still reports no description.
2. **Pull and verify the latest code.** Check that `laptop/vision/local_vision.py` includes the 1280-pixel image preprocessing, `keep_alive: 5m`, and 180-second timeouts. Restart the dashboard after updating.
3. **Re-run the small generated image through Ai-Glasses.** This isolates the model pipeline from phone networking.
4. **Re-test the phone snapshot.** Confirm `/shot.jpg` opens in the laptop browser, then use Capture & analyze.
5. **Run tests and inspect CI** on the latest default-branch commit.
6. **Perform the offline laptop demo rehearsal.**
7. **Only then** proceed to physical hardware integration.

## Definition of done

The project is demo-ready when all of the following are true:

- The laptop can set up and launch from documented instructions.
- Text, memory, speech, transcription, OCR, and vision have each been smoke-tested.
- A phone snapshot can be analyzed locally through the application.
- Camera and microphone privacy defaults and revocation behavior are verified.
- Unit tests, compilation checks, firmware build, and current CI checks pass.
- The laptop-only demo works without internet after initial downloads.
- Physical hardware claims are limited to behavior actually tested on the exact board.
