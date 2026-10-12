# Security and Privacy Notes

**Project:** Ai-Spects / Ai-Glasses  
**Review date:** 12 October 2026  
**Scope:** Local laptop dashboard, paired ESP32 device, camera/microphone uploads, local vision, and optional private-LAN access.

This is a prototype security guide, not a professional penetration-test report.

## Protections implemented in code
- Device routes verify a locally stored pairing token using constant-time comparison.
- Optional LAN dashboard routes verify a PIN stored locally.
- Dashboard camera and device microphone permissions default off.
- Camera capture requires an active, unexpired request, dashboard permission, recent device status, camera-enabled status, physical-switch report, and indicator report.
- Server rechecks key privacy signals after upload finishes.
- Glasses camera upload is limited to 8 MiB and requires a JPEG signature.
- Firmware limits an individual frame and checks its physical switch before upload.
- Device audio upload is blocked unless microphone permission is enabled; audio size is limited and temporary files are deleted in a cleanup path.
- Phone-camera input is restricted to private-LAN IP addresses and expected snapshot paths, with size and content-signature checks.
- Phone-camera and optional MJPEG fetches use no-redirect helpers.
- Local vision rejects a non-loopback Ollama host.
- Runtime data, recordings, captures, models, local credentials, and virtual environments are ignored by Git.
- Vision diagnostics should contain operational metadata only, never image payload/base64.

## Required operating rules
1. Keep localhost mode as default. Do not expose the dashboard to other interfaces unless LAN mode is intentionally configured.
2. Never port-forward or publicly expose the dashboard. PIN protection is not a substitute for a hardened internet-facing service.
3. LAN mode is only for trusted private Wi-Fi. Use a unique PIN and keep the PIN file out of Git, screenshots, and shared logs.
4. Protect the pairing token. Keep it private and rotate it if exposed.
5. Do not commit Wi-Fi credentials. Keep firmware secrets in a local ignored file based on the example template.
6. Use camera and microphone only when needed. Turn permissions off after a test. The firmware switch is a software gate, not an electrical camera power disconnect.
7. Never log image bytes, base64 payloads, audio content, PINs, or device tokens.
8. Use only private-LAN camera endpoints. Do not fetch arbitrary public hosts or follow redirects.
9. Avoid public Wi-Fi for shared-device demos. Prefer localhost or a trusted isolated network.
10. Treat local memory as private. SQLite can contain saved facts and optional summaries. Keep it out of Git and clear it before sharing the laptop.
11. Review dependency updates and rerun tests after changes.
12. Do not connect a battery or charging module until voltage, polarity, protection, wiring, and ratings are checked by an experienced adult/technician.

## Security test checklist
- [ ] Missing/incorrect device token returns 401.
- [ ] Missing/incorrect dashboard PIN returns 401 in LAN mode.
- [ ] LAN mode without a PIN file fails closed.
- [ ] Camera and microphone start disabled.
- [ ] Device microphone upload is rejected while permission is off.
- [ ] Camera upload is rejected without an active request.
- [ ] Expired capture requests are rejected.
- [ ] Stale heartbeat, camera-disabled state, switch-off, or indicator-off blocks capture.
- [ ] Invalid JPEG signatures and oversized images are rejected.
- [ ] Permission revocation during upload/capture prevents acceptance or analysis.
- [ ] Public IPs, hostnames, unexpected camera paths, and redirects are rejected.
- [ ] Remote Ollama host is rejected.
- [ ] Test logs and Git diff contain no credentials or image payloads.

## Known limits
- Heartbeat is a firmware report, not cryptographic proof that a physical switch or LED is truly in the stated state.
- The switch and indicator must be observed on the actual board. The switch does not physically disconnect camera power.
- The dashboard PIN is a prototype LAN safeguard, not production authentication.
- Unless TLS is configured separately, LAN traffic is not end-to-end encrypted. Keep it on a trusted private network.
- This project has not been independently penetration-tested.
- Physical wiring, speaker, microphone, power, and battery safety are not validated by software tests.
- Passing a unit test or firmware compile does not prove hardware safety.

## Incident response
If a PIN, token, Wi-Fi password, recording, or captured frame is exposed:
1. Stop the app/device and disable camera/microphone permissions.
2. Remove exposed material from active configuration and rotate the relevant credential.
3. Check recent commits. Deleting a file in a new commit does not erase it from old Git history.
4. Clear temporary captures/audio and review local logs.
5. Re-run privacy tests before using the prototype again.

## Before each demo
- [ ] Start in localhost mode unless trusted-LAN pairing is necessary.
- [ ] Confirm camera and microphone are disabled.
- [ ] Confirm no credentials are staged for Git.
- [ ] Confirm indicator and physical switch on the real board.
- [ ] Keep the app inaccessible from public networks.
- [ ] Turn permissions off when the demo ends.
