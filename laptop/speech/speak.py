from __future__ import annotations

import subprocess
import shutil


class SpeechOutputError(RuntimeError):
    pass


def speak_local(text: str) -> dict:
    """Speak via installed local eSpeak NG if present; never uses a cloud TTS API.

    Telugu voice quality depends on the installed eSpeak NG voice data and must be
    evaluated on the target machine. Text remains the reliable fallback.
    """
    text = text.strip()
    if not text:
        return {"spoken": False, "reason": "empty_text"}
    executable = shutil.which("espeak-ng") or shutil.which("espeak-ng.exe")
    if not executable:
        return {
            "spoken": False,
            "reason": "espeak-ng-not-installed",
            "message": "Offline speech output is unavailable; show the answer as text.",
        }
    try:
        subprocess.Popen(
            [executable, "-s", "155", text],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError as exc:
        raise SpeechOutputError("Could not start the local speech engine.") from exc
    return {"spoken": True, "engine": "eSpeak NG", "offline": True}
