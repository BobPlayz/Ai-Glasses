from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import threading
import wave
from pathlib import Path

import httpx


class SpeechOutputError(RuntimeError):
    pass


ROOT = Path(__file__).resolve().parents[2]
VOICE_DIR = ROOT / "models" / "tts"
FISH_KEY_PATH = ROOT / ".fish-audio-key"
FISH_VOICE_ID = "e13fa398a7f445a685316a3de6089ce7"
FISH_MODEL = "s2.1-pro-free"
_voice_cache: dict[str, object] = {}
_voice_lock = threading.Lock()
_synthesis_lock = threading.Lock()


def _is_telugu(text: str) -> bool:
    return any("\u0c00" <= char <= "\u0c7f" for char in text)


def _fish_api_key() -> str:
    key = os.environ.get("FISH_AUDIO_API_KEY", "").strip()
    if key:
        return key
    try:
        return FISH_KEY_PATH.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _speak_with_fish(text: str) -> dict | None:
    """Use the user's selected Fish Audio voice for English; the API needs internet."""
    if _is_telugu(text):
        return None
    api_key = _fish_api_key()
    if not api_key:
        return None

    import winsound

    response = httpx.post(
        "https://api.fish.audio/v1/tts",
        headers={
            "Authorization": f"Bearer {api_key}",
            "model": FISH_MODEL,
            "Content-Type": "application/json",
        },
        json={
            "text": text[:1200],
            "reference_id": FISH_VOICE_ID,
            "format": "wav",
            "normalize": True,
        },
        timeout=httpx.Timeout(90.0, connect=15.0),
    )
    if response.status_code >= 400:
        detail = response.text[:240].replace("\n", " ")
        raise SpeechOutputError(
            f"Fish Audio voice request failed (HTTP {response.status_code}). "
            f"Check your API key and Fish Audio quota. {detail}"
        )
    if not response.content:
        raise SpeechOutputError("Fish Audio returned an empty audio response.")

    with tempfile.NamedTemporaryFile(prefix="glasses-fish-", suffix=".wav", delete=False) as temp:
        output_path = Path(temp.name)
        temp.write(response.content)
    try:
        with _synthesis_lock:
            winsound.PlaySound(str(output_path), winsound.SND_FILENAME)
    finally:
        output_path.unlink(missing_ok=True)

    return {
        "spoken": True,
        "engine": "Fish Audio",
        "voice": FISH_VOICE_ID,
        "model": FISH_MODEL,
        "offline": False,
    }


def _speak_with_kokoro(text: str) -> dict | None:
    """Offline English fallback if the Fish Audio key is absent or its service is unavailable."""
    if _is_telugu(text):
        return None
    try:
        import numpy as np
        import soundfile as sf
        import winsound
        from kokoro import KPipeline

        with _voice_lock:
            pipeline = _voice_cache.get("kokoro-b")
            if pipeline is None:
                pipeline = KPipeline(lang_code="b")
                _voice_cache["kokoro-b"] = pipeline

        chunks = []
        with _synthesis_lock:
            for _graphemes, _phonemes, audio in pipeline(
                text[:1200], voice="bm_george", speed=0.94, split_pattern=r"\n+"
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
            "voice": "bm_george (British English fallback)",
            "offline": True,
        }
    except Exception:
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
    """Prefer the selected Fish Audio voice for English; keep Telugu and offline fallbacks local."""
    text = text.strip()
    if not text:
        return {"spoken": False, "reason": "empty_text"}

    if not _is_telugu(text) and _fish_api_key():
        try:
            fish_result = _speak_with_fish(text)
            if fish_result:
                return fish_result
        except httpx.HTTPError as exc:
            # A temporary network failure should not stop the glasses from speaking.
            fish_error = f"Fish Audio connection failed: {exc.__class__.__name__}"
        except SpeechOutputError as exc:
            # Report configuration/quota errors instead of silently pretending Fish spoke.
            return {
                "spoken": False,
                "engine": "Fish Audio",
                "reason": "fish_audio_failed",
                "message": str(exc),
                "offline": False,
            }
        else:
            fish_error = ""
    else:
        fish_error = ""

    kokoro_result = _speak_with_kokoro(text)
    if kokoro_result:
        if fish_error:
            kokoro_result["fallback_reason"] = fish_error
        return kokoro_result

    piper_result = _speak_with_piper(text)
    if piper_result:
        if fish_error:
            piper_result["fallback_reason"] = fish_error
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
            **({"fallback_reason": fish_error} if fish_error else {}),
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
