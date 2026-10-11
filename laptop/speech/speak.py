from __future__ import annotations

import threading


class SpeechOutputError(RuntimeError):
    pass


_voice_lock = threading.Lock()


def _is_telugu(text: str) -> bool:
    return any("\u0c00" <= char <= "\u0c7f" for char in text)


def speak_local(text: str) -> dict:
    """Speak using installed Windows voices only. No cloud service or API key is used."""
    text = text.strip()
    if not text:
        return {"spoken": False, "reason": "empty_text"}

    try:
        import pyttsx3

        with _voice_lock:
            engine = pyttsx3.init()
            voices = engine.getProperty("voices") or []
            requested_telugu = _is_telugu(text)
            hints = ("telugu", "te-in", "te_in", "tel")
            chosen = None

            if requested_telugu:
                for voice in voices:
                    searchable = (
                        str(getattr(voice, "id", "")) + " "
                        + str(getattr(voice, "name", "")) + " "
                        + str(getattr(voice, "languages", ""))
                    ).casefold()
                    if any(hint in searchable for hint in hints):
                        chosen = voice
                        break

            if chosen is None and voices:
                for voice in voices:
                    searchable = (
                        str(getattr(voice, "id", "")) + " "
                        + str(getattr(voice, "name", ""))
                    ).casefold()
                    if "india" in searchable or "en-in" in searchable or "en_in" in searchable:
                        chosen = voice
                        break

            if chosen is not None:
                engine.setProperty("voice", chosen.id)
            engine.setProperty("rate", 175)
            engine.say(text[:1200])
            engine.runAndWait()
            engine.stop()

        telugu_found = bool(
            chosen and any(
                hint in (
                    str(getattr(chosen, "id", "")) + " "
                    + str(getattr(chosen, "name", ""))
                ).casefold()
                for hint in hints
            )
        )
        return {
            "spoken": True,
            "engine": "Windows SAPI / installed offline voice",
            "voice": str(getattr(chosen, "name", "Windows default voice")) if chosen else "Windows default voice",
            "offline": True,
            "telugu_voice_found": telugu_found,
        }
    except Exception as exc:
        raise SpeechOutputError(
            "Windows offline speech failed. Check that a Windows text-to-speech voice is installed and audio is enabled."
        ) from exc
