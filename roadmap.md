# AI-Spects Roadmap

**Repository:** BobPlayz/Ai-Glasses  
**Last reviewed:** 12 October 2026  
**Rule:** A phase is complete only when its exit checks are demonstrated. A passing build is not proof of physical hardware operation.

## Phase 1 of 10: Project foundation and setup
**Status: Software foundation built; final clean setup rehearsal remains.**
- [x] Windows setup/launch scripts, dependencies, runtime folders, Git ignore rules.
- [x] Local FastAPI dashboard and documented launch path.
- [ ] Verify clean setup and launch after reboot.
**Exit check:** Clean setup launches without manually repairing the environment.

## Phase 2 of 10: Local AI and memory
**Status: Implemented; full offline acceptance run remains.**
- [x] Local Ollama text inference with Qwen 2.5 1.5B primary and smaller fallback.
- [x] SQLite useful-fact memory, search, delete/clear, opt-in summaries, recent dialogue context.
- [x] Separate Gen Z style toggle.
- [ ] Test memory persistence/retrieval and fallback after restart.
- [ ] Confirm no model downloads are needed during offline use.
**Exit check:** Text AI and memory work offline with cached models.

## Phase 3 of 10: Speech and language
**Status: Software paths implemented; actual glasses audio unverified.**
- [x] Local Whisper transcription adapter.
- [x] Piper offline speech and Windows speech fallback.
- [x] Optional online neural English/Telugu voice with saved preference.
- [x] Wake phrase, Telugu visual-question phrases, phrase-level streaming, bounded device WAV queue.
- [ ] Test English and everyday Telugu speech/transcription offline.
- [ ] Confirm assets are cached and measure latency.
**Exit check:** Voice works offline and selected mode is reported accurately.

## Phase 4 of 10: Dashboard and controls
**Status: Built; manual checks remain.**
- [x] Dark/cyan reactor identity with AI Core, Vision, and Settings.
- [x] Camera, microphone, memory, speech, wake phrase, and style controls.
- [x] Camera and device microphone permissions default off.
- [ ] Verify every control changes backend state and test recovery after service failure.
**Exit check:** Dashboard state is accurate and disconnected features are not presented as working.

## Phase 5 of 10: Security and privacy
**Status: Protections implemented; adversarial/manual tests remain.**
- [x] Device pairing token; optional PIN-protected LAN dashboard mode.
- [x] Camera/microphone default-off permissions and revocation controls.
- [x] Expiring capture requests, fresh status, physical-switch and indicator reports.
- [x] Bounded request bodies, bounded device audio reads, JPEG signature checks, private-LAN camera URL validation, redirect blocking.
- [x] Baseline security headers and 20-megapixel / single-frame image validation before OCR and inference.
- [x] Cryptographically random dashboard PIN generation; no PIN printed during setup.
- [x] Local vision rejects non-loopback Ollama hosts; runtime secrets/data ignored by Git.
- [ ] Test expired requests, stale status, switch-off during capture, invalid uploads, and bad tokens.
- [ ] Review logs and Git changes for secrets or captured media.
- [ ] Never expose the prototype directly to the public internet.
**Exit check:** Privacy tests pass and revocation is demonstrated. Software switch reporting is not an electrical camera disconnect.

## Phase 6 of 10: Vision pipeline
**Status: Diagnostics and mocked regression tests added; full app flow still needs proof.**
- [x] Local Ollama image description and optional English/Telugu OCR.
- [x] Image resize/compression, bounded retry, actionable HTTP/timeout/invalid-JSON errors.
- [x] Safe diagnostics without image payload logging; regression tests for retry and failure paths.
- [x] Earlier direct Ollama generated-image baseline succeeded on the laptop.
- [ ] Get current Python CI green after request-body and image-validation hardening.
- [ ] Test a generated image through the dashboard endpoint, then a real snapshot.
**Exit check:** A real image returns a useful answer through Ai-Spects itself.

## Phase 7 of 10: Firmware and device protocol
**Status: Candidate firmware compiles; actual board behavior is unverified.**
- [x] Candidate XIAO ESP32-S3 Sense firmware for heartbeat, one-shot camera, switch gating, mic chunks, protocol.
- [x] Switch check before upload and frame-size limit.
- [x] Microphone pin docs corrected: GPIO42 PDM clock, GPIO41 PDM data.
- [x] GitHub Actions checks Python tests and firmware compilation.
- [ ] Confirm exact board revision/pinout and keep credentials out of commits.
- [ ] Flash only after pin and power checks.
**Exit check:** Pairing, heartbeat, and privacy behavior are observed on the actual board.

## Phase 8 of 10: Camera, speaker, wearable assembly
**Status: Not physically verified.**
- [x] Candidate hardware and side/behind-ear mounting approach documented.
- [x] Candidate I2S output GPIO4/5/6 documented; wiring is unconfirmed.
- [ ] Confirm amplifier/speaker ratings, power module, cable, and board revision.
- [ ] Bench-test on USB first; check continuity, polarity, insulation, and shorts.
- [ ] Verify camera, indicator, microphone, and glasses-speaker playback.
- [ ] Do not connect battery/charging until reviewed by an experienced adult/technician.
**Exit check:** Physical components work safely together on the assembled device.

## Phase 9 of 10: Offline exhibition rehearsal
**Status: Planned.**
- [ ] Cache models, OCR language data, Whisper, and offline voices.
- [ ] Disconnect internet and test text, memory, English/Telugu speech, transcription, OCR, vision.
- [ ] Demonstrate privacy defaults, physical switch, indicator, and permission revocation.
- [ ] Record real latency and fallback behavior; prepare laptop-only fallback.
**Exit check:** Demo repeats offline after initial downloads, with limitations stated honestly.

## Phase 10 of 10: Final acceptance and future integration
**Status: Future work after the exhibition-critical build is stable.**
- [ ] Run Python tests, compile checks, firmware build, and review current CI.
- [ ] Resolve failures before calling software release-ready.
- [ ] Complete privacy and hardware checklist; tag a known-good demo version.
- [ ] Consider BobAI integration after core glasses behavior is stable.
- [ ] Treat an AR display as separate future work, not a verified feature.
**Exit check:** Software checks are green, hardware claims are physically tested, and demo/recovery steps are documented.

## Immediate priority order
1. Get Python tests and the new dependency audit green.
2. Exercise request-size limits and malformed/pixel-bomb image rejection.
3. Test vision through Ai-Spects, not only direct Ollama.
4. Rehearse offline mode and record latency.
5. Verify the exact board and safe power/audio path.
6. Run the exhibition rehearsal.

## Definition of done
Documented setup works; local AI, memory, speech, and vision are tested through the application; privacy checks pass; offline rehearsal succeeds; hardware claims match physical evidence.
