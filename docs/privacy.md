# Privacy requirements

- No cloud inference or uploads in the offline demo.
- Raw audio recording disabled by default.
- Camera capture only after the user asks a visual question.
- A physical privacy switch must prevent capture when disabled; dashboard state alone is insufficient.
- Show a hardware indicator during capture and mirror its state on the dashboard.
- Keep local memory inspectable and deletable, stored on the laptop.
- Protect access before enabling phone/LAN control.
- Never commit recordings, photos, SQLite databases, model files, passwords, tokens, or private transcripts.
- Test with internet disconnected and camera privacy switch disabled.
- Get consent before capturing other people during tests.
