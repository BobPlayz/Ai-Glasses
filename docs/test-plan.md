# Test plan

## Laptop scaffold
- [ ] Run setup.ps1 on Windows 11.
- [ ] Run launch.ps1 and open the dashboard.
- [ ] Save memory, restart the app, verify persistence.
- [ ] Delete one memory and clear all memories.
- [ ] Confirm /api/ask says the model is not configured.
- [ ] Confirm camera and microphone show unavailable.

## AI integration
- [ ] Run local model without internet.
- [ ] Measure response latency and RAM use.
- [ ] Test English and everyday Andhra Telugu recognition.
- [ ] Test short spoken and long text responses.
- [ ] Test local vision and OCR separately.
- [ ] Confirm no cloud endpoints are called.

## Hardware
- [ ] Camera frame arrives over local Wi-Fi.
- [ ] Microphone stream arrives with acceptable latency.
- [ ] Physical switch disables capture.
- [ ] Indicator illuminates whenever capture is active.
- [ ] Device reconnects after Wi-Fi interruption.
- [ ] Test with internet disconnected and on the exhibition network.

## Demo
- [ ] Repeat the full live demo successfully at least three times.
- [ ] Confirm no secrets or private data are in Git.
- [ ] Label backup video as backup.
- [ ] Label every feature as implemented, laptop-tested, or physical-device-tested.
