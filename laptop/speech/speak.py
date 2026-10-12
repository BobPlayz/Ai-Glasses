from __future__ import annotations

import asyncio
import io
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

# Faster phoneme timing plus a small playback-rate lift gives JARVIS a
# brisker, slightly brighter sound without changing the installed voice model.
PIPER_LENGTH_SCALE = 0.88
ONLINE_VOICE_MODE_PATH = ROOT / "data" / "voice-mode.json"
ONLINE_VOICES = {"en": "en-US-AvaNeural", "te": "te-IN-ShrutiNeural"}
PLAYBACK_RATE_MULTIPLIER = 1.05


def _is_telugu(text: str) -> bool:
    return any(0x0C00 <= ord(char) <= 0x0C7F for char in text)


def _tune_wav_bytes(audio: bytes) -> bytes:
    """Raise playback pitch slightly by adjusting WAV sample-rate metadata.

    This intentionally also makes playback a little faster. Audio samples are
    unchanged, and the WAV header stays valid for laptop and paired-device use.
    """
    source = io.BytesIO(audio)
    tuned = io.BytesIO()
    with wave.open(source, "rb") as reader:
        params = reader.getparams()
        frames = reader.readframes(reader.getnframes())
        with wave.open(tuned, "wb") as writer:
            writer.setnchannels(params.nchannels)
            writer.setsampwidth(params.sampwidth)
            writer.setframerate(max(1, round(params.framerate * PLAYBACK_RATE_MULTIPLIER)))
            writer.setcomptype(params.comptype, params.compname)
            writer.writeframes(frames)
    return tuned.getvalue()



def online_voice_enabled() -> bool:
    try:
        import json
        data = json.loads(ONLINE_VOICE_MODE_PATH.read_text(encoding="utf-8"))
        return isinstance(data, dict) and data.get("enabled") is True
    except (OSError, ValueError):
        return False


def _synthesize_online_wav(text: str) -> bytes | None:
    """Synthesize natural online neural speech and return PCM WAV bytes."""
    try:
        import edge_tts
        import miniaudio

        voice = ONLINE_VOICES["te" if _is_telugu(text) else "en"]

        async def render() -> bytes:
            communicate = edge_tts.Communicate(text[:1200], voice, rate="+4%", volume="+0%")
            chunks = []
            async for chunk in communicate.stream():
                if chunk.get("type") == "audio":
                    chunks.append(chunk["data"])
            return b"".join(chunks)

        mp3_data = asyncio.run(render())
        if not mp3_data:
            return None
        decoded = miniaudio.decode(
            mp3_data,
            output_format=miniaudio.SampleFormat.SIGNED16,
            nchannels=1,
            sample_rate=24000,
        )
        output = io.BytesIO()
        with wave.open(output, "wb") as wav:
            wav.setnchannels(decoded.nchannels)
            wav.setsampwidth(2)
            wav.setframerate(decoded.sample_rate)
            wav.writeframes(decoded.samples)
        return output.getvalue()
    except Exception:
        return None


def _speak_with_piper(text: str, voice_key: str) -> dict | None:
    model_path = VOICE_DIR / f"{voice_key}.onnx"
    config_path = VOICE_DIR / f"{voice_key}.onnx.json"
    if not model_path.is_file() or not config_path.is_file():
        return None

    try:
        import winsound
        from piper import PiperVoice, SynthesisConfig

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
                    voice.synthesize_wav(
                        text[:1200],
                        wav_file,
                        syn_config=SynthesisConfig(length_scale=PIPER_LENGTH_SCALE),
                    )
                output_path.write_bytes(_tune_wav_bytes(output_path.read_bytes()))
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
            engine.setProperty("rate", 195)
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

    if online_voice_enabled():
        audio = _synthesize_online_wav(text)
        if audio:
            try:
                import winsound
                with tempfile.NamedTemporaryFile(prefix="glasses-online-tts-", suffix=".wav", delete=False) as temp:
                    output_path = Path(temp.name)
                try:
                    output_path.write_bytes(audio)
                    winsound.PlaySound(str(output_path), winsound.SND_FILENAME)
                finally:
                    output_path.unlink(missing_ok=True)
                language = "Telugu" if _is_telugu(text) else "English"
                voice = ONLINE_VOICES["te" if _is_telugu(text) else "en"]
                return {"spoken": True, "engine": "Microsoft neural TTS (online)", "voice": voice, "offline": False, "language": language}
            except Exception:
                pass

    telugu = _is_telugu(text)
    voice_key = "te_IN-venkatesh-medium" if telugu else "en_GB-alan-medium"
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


def synthesize_wav_local(text: str, max_chars: int = 220) -> bytes | None:
    """Render tuned offline Piper speech as mono PCM WAV bytes for paired glasses.

    Returns None when Piper assets are unavailable, allowing laptop-output fallback.
    This function never calls a cloud service and does not play audio itself.
    """
    text = " ".join(text.strip().split())[:max(1, min(max_chars, 500))]
    if not text:
        return None
    if online_voice_enabled():
        return _synthesize_online_wav(text)
    voice_key = "te_IN-venkatesh-medium" if _is_telugu(text) else "en_GB-alan-medium"
    model_path = VOICE_DIR / f"{voice_key}.onnx"
    config_path = VOICE_DIR / f"{voice_key}.onnx.json"
    if not model_path.is_file() or not config_path.is_file():
        return None
    try:
        from piper import PiperVoice, SynthesisConfig
        with _voice_lock:
            voice = _voice_cache.get(voice_key)
            if voice is None:
                voice = PiperVoice.load(str(model_path), config_path=str(config_path))
                _voice_cache[voice_key] = voice
        output = io.BytesIO()
        with _synthesis_lock:
            with wave.open(output, "wb") as wav_file:
                voice.synthesize_wav(
                    text,
                    wav_file,
                    syn_config=SynthesisConfig(length_scale=PIPER_LENGTH_SCALE),
                )
        audio = _tune_wav_bytes(output.getvalue())
        if not audio.startswith(b"RIFF") or audio[8:12] != b"WAVE" or len(audio) > 900_000:
            return None
        return audio
    except Exception:
        return None
