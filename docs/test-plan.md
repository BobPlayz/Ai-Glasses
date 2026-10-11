# Test plan

## Automated laptop checks
- [ ] Python compileall passes
- [ ] Unit tests pass
- [ ] Dashboard PIN is required in LAN mode
- [ ] Device token is required for device endpoints
- [ ] Camera capture is refused when dashboard control is off
- [ ] Wake phrase normalization supports English and Telugu characters

## Laptop runtime
- [ ] Run setup.ps1 on Windows 11.
- [ ] Open dashboard in localhost mode.
- [ ] Save memory, restart the app, verify persistence.
- [ ] Delete one memory and clear all memories.
- [ ] Ask in English and everyday Andhra Telugu.
- [ ] Confirm the smaller model fallback can answer when primary is unavailable/too slow.
- [ ] Verify local speech output and actual Telugu voice quality.
- [ ] Transcribe an audio file while internet is disconnected.
- [ ] Ask a question about a chosen image while internet is disconnected.

## Physical device
- [ ] Confirm exact board revision and pin map before wiring.
- [ ] Compile firmware and flash over USB.
- [ ] Device connects to trusted local Wi-Fi and authenticates.
- [ ] Camera control disabled: camera driver stays stopped and no capture is accepted.
- [ ] Dashboard enabled plus physical switch enabled: indicator lights during capture and frame arrives.
- [ ] Physical switch off: capture is refused and camera driver stops.
- [ ] Microphone sends short WAV chunks, wake phrase arms the assistant, question is collected until a pause, local answer is returned.
- [ ] Device reconnects after Wi-Fi interruption.
- [ ] Confirm no raw audio files remain in the temp folder.

## Offline demo
- [ ] Disconnect internet and repeat the complete demo successfully at least three times.
- [ ] Confirm all required models are already cached.
- [ ] Rehearse on the actual exhibition network and laptop speakers.
- [ ] Keep backup video clearly labelled as backup.
- [ ] Do not capture visitors without permission.
- [ ] Mark every result as code-tested, laptop-tested, or physical-device-tested.
