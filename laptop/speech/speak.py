from __future__ import annotations

import shutil
import subprocess
import threading


class SpeechOutputError(RuntimeError):
    pass


_speech_lock = threading.Lock()


def speak_local(text: str) -> dict:
    """Speak offline using Windows' installed voices, then eSpeak NG if available.

    Voice quality and Telugu availability depend on voices installed on the target
    computer. This function never uses a cloud TTS API.
    """
    text = text.strip()
    if not text:
        return {"spoken": False, "reason": "empty_text"}

    # SAPI5 on Windows often provides more natural installed voices than eSpeak.
    try:
        import pyttsx3
        with _speech_lock:
            engine = pyttsx3.init()
            voices = engine.getProperty("voices") or []
            language_hints = ("telugu", "te-in", "te_in", "tel")
            requested_telugu = any(ch in text for ch in "తెలుగు")
            chosen = None
            if requested_telugu:
                for voice in voices:
                    searchable = (str(getattr(voice, "id", "")) + " " + str(getattr(voice, "name", "")) + " " + str(getattr(voice, "languages", ""))).casefold()
                    if any(hint in searchable for hint in language_hints):
                        chosen = voice
                        break
            if chosen is None and voices:
                # Prefer an Indian English voice for English or when Telugu is absent.
                for voice in voices:
                    searchable = (str(getattr(voice, "id", "")) + " " + str(getattr(voice, "name", ""))).casefold()
                    if "india" in searchable or "en-in" in searchable or "en_in" in searchable:
                        chosen = voice
                        break
            if chosen is not None:
                engine.setProperty("voice", chosen.id)
            engine.setProperty("rate", 165)
            engine.say(text[:1200])
            engine.runAndWait()
            engine.stop()
        return {
            "spoken": True,
            "engine": "Windows SAPI / installed offline voice",
            "offline": True,
            "telugu_voice_found": bool(chosen and any(h in (str(getattr(chosen, "id", "")) + str(getattr(chosen, "name", ""))).casefold() for h in language_hints)),
        }
    except Exception:
        pass

    executable = shutil.which("espeak-ng") or shutil.which("espeak-ng.exe")
    if executable:
        try:
            subprocess.run(
                [executable, "-s", "155", text[:1200]],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=30,
                check=False,
            )
            return {"spoken": True, "engine": "eSpeak NG", "offline": True, "voice_quality": "basic"}
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise SpeechOutputError("Could not start the local speech engine.") from exc

    return {
        "spoken": False,
        "reason": "no-local-speech-engine",
        "message": "No offline speech engine is available. The answer remains available as text.",
    }
