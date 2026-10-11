from __future__ import annotations

import shutil
import subprocess
import tempfile
import threading
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
    return any("\u0c00" <= char <= "\u0c7f" for char in text)


def _speak_with_kokoro(text: str) -> dict | None:
    """Use Kokoro's more expressive British voice for English when installed and cached."""
    if _is_telugu(text):
        return None
    try:
        import numpy as np
        import soundfile as sf
        import winsound
        from kokoro import KPipeline

        # 'b' selects Kokoro's British-English pipeline; bm_george is a calm
        # British male voice. Keep the pipeline resident to avoid reload delays.
        with _voice_lock:
            pipeline = _voice_cache.get("kokoro-b")
            if pipeline is None:
                pipeline = KPipeline(lang_code="b")
                _voice_cache["kokoro-b"] = pipeline

        chunks = []
        with _synthesis_lock:
            for _graphemes, _phonemes, audio in pipeline(
                text[:1200],
                voice="bm_george",
                speed=0.94,
                split_pattern=r"\n+",
            ):
                if audio is not None and len(audio):
                    chunks.append(np.asarray(audio, dtype=np.float32))
            if not chunks:
                return None

            audio = np.concatenate(chunks)
            with tempfile.NamedTemporaryFile(prefix="glasses-kokoro-", suffix=".wav", delete=False) as temp:
                output_path = Path(temp.name)
            try:
                sf.write(str(output_path), audio, 24000, subtype="PCM_16")
                winsound.PlaySound(str(output_path), winsound.SND_FILENAME)
            finally:
                output_path.unlink(missing_ok=True)

        return {
            "spoken": True,
            "engine": "Kokoro neural TTS",
            "voice": "bm_george (British English)",
            "offline": True,
        }
    except Exception:
        # Never break the glasses if Kokoro isn't installed or its assets aren't cached.
        return None


def _speak_with_piper(text: str) -> dict | None:
    """Offline fallback for English and Telugu."""
    voice_key = "te_IN-maya-medium" if _is_telugu(text) else "en_GB-alan-medium"
    model_path = VOICE_DIR / f"{voice_key}.onnx"
    config_path = VOICE_DIR / f"{voice_key}.onnx.json"
    if not model_path.is_file() or not config_path.is_file():
        return None

    try:
        from piper import PiperVoice
        import winsound

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
        }
    except Exception:
        return None


def speak_local(text: str) -> dict:
    """Prefer Kokoro for natural English, retaining Piper for Telugu and offline fallback."""
    text = text.strip()
    if not text:
        return {"spoken": False, "reason": "empty_text"}

    kokoro_result = _speak_with_kokoro(text)
    if kokoro_result:
        return kokoro_result

    piper_result = _speak_with_piper(text)
    if piper_result:
        return piper_result

    try:
        import pyttsx3
        with _voice_lock:
            engine = pyttsx3.init()
            voices = engine.getProperty("voices") or []
            requested_telugu = _is_telugu(text)
            language_hints = ("telugu", "te-in", "te_in", "tel")
            chosen = None
            if requested_telugu:
                for voice in voices:
                    searchable = (str(getattr(voice, "id", "")) + " " + str(getattr(voice, "name", "")) + " " + str(getattr(voice, "languages", ""))).casefold()
                    if any(hint in searchable for hint in language_hints):
                        chosen = voice
                        break
            if chosen is None and voices:
                for voice in voices:
                    searchable = (str(getattr(voice, "id", "")) + " " + str(getattr(voice, "name", ""))).casefold()
                    if "india" in searchable or "en-in" in searchable or "en_in" in searchable:
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
            "offline": True,
            "telugu_voice_found": bool(chosen and any(h in (str(getattr(chosen, "id", "")) + str(getattr(chosen, "name", ""))).casefold() for h in language_hints)),
        }
    except Exception:
        pass

    executable = shutil.which("espeak-ng") or shutil.which("espeak-ng.exe")
    if executable:
        try:
            subprocess.run(
                [executable, "-s", "170", text[:1200]],
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
        "message": "No offline speech engine or cached voice is available. The answer remains available as text.",
    }
