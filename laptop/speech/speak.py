from __future__ import annotations

import threading
import tempfile
import wave
from pathlib import Path


class SpeechOutputError(RuntimeError):
    pass


ROOT = Path(__file__).resolve().parents[2]
VOICE_DIR = ROOT / "models" / "tts"
_voice_cache: dict[str, object] = {}
_voice_lock = threading.Lock()
_synthesis_lock = threading.Lock()


def _is_telugu(text: str) -> bool:
    return any("\\u0c00" <= char <= "\\u0c7f" for char in text)


def _speak_with_piper(text: str, voice_key: str) -> dict | None:
    model_path = VOICE_DIR / f"{voice_key}.onnx"
    config_path = VOICE_DIR / f"{voice_key}.onnx.json"
    if not model_path.is_file() or not config_path.is_file():
        return None

    try:
        import winsound
        from piper import PiperVoice

        with _voice_lock:
            voice = _voice_cache.get(voice_key)
            if voice is None:
                voice = PiperVoice.load(str(model_path), config_path=str(config_path))
                _voice_cache[voice_key] = voice

        with tempfile.NamedTemporaryFile(prefix="glasses-tts-", suffix=".wav", delete=False) as temp:
            output_path = Path(temp.name)
        try:
            with _synthesis_lock:
                with wave.open(str(output_path), "wb") as wav_file:
                    voice.synthesize_wav(text[:1200], wav_file)
                winsound.PlaySound(str(output_path), winsound.SND_FILENAME)
        finally:
            output_path.unlink(missing_ok=True)

        return {
            "spoken": True,
            "engine": "Piper neural TTS",
            "voice": voice_key,
            "offline": True,
            "language": "Telugu" if voice_key.startswith("te_") else "English",
        }
    except Exception:
        return None


def _speak_with_windows(text: str) -> dict | None:
    try:
        import pyttsx3

        with _voice_lock:
            engine = pyttsx3.init()
            voices = engine.getProperty("voices") or []
            chosen = None
            hints = ("india", "en-in", "en_in")
            for voice in voices:
                searchable = (
                    str(getattr(voice, "id", "")) + " "
                    + str(getattr(voice, "name", ""))
                ).casefold()
                if any(hint in searchable for hint in hints):
                    chosen = voice
                    break
            if chosen is not None:
                engine.setProperty("voice", chosen.id)
            engine.setProperty("rate", 175)
            engine.say(text[:1200])
            engine.runAndWait()
            engine.stop()

        return {
            "spoken": True,
            "engine": "Windows SAPI / installed offline voice",
            "voice": str(getattr(chosen, "name", "Windows default voice")) if chosen else "Windows default voice",
            "offline": True,
            "language": "English",
        }
    except Exception:
        return None


def speak_local(text: str) -> dict:
    """Use offline Piper neural English/Telugu voices; never calls a cloud TTS API."""
    text = text.strip()
    if not text:
        return {"spoken": False, "reason": "empty_text"}

    telugu = _is_telugu(text)
    voice_key = "te_IN-maya-medium" if telugu else "en_GB-alan-medium"
    result = _speak_with_piper(text, voice_key)
    if result:
        return result

    if telugu:
        return {
            "spoken": False,
            "engine": "Piper neural TTS",
            "reason": "telugu_voice_not_installed",
            "message": "The offline Telugu voice files are missing. Run scripts\\install_british_voice.ps1 to install both English and Telugu voice files.",
            "offline": True,
        }

    result = _speak_with_windows(text)
    if result:
        result["fallback_reason"] = "Piper English voice files are missing or could not be loaded."
        return result

    raise SpeechOutputError(
        "Offline speech failed. Install the Piper voice files or check that a Windows speech voice is installed."
    )
