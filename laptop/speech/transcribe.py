from __future__ import annotations

import os
from pathlib import Path


class SpeechError(RuntimeError):
    pass


def transcribe_audio_file(audio_path: str | Path, model_size: str | None = None) -> dict:
    """Transcribe an audio file using a cached local faster-whisper model.

    The model is never downloaded implicitly by this function. Setup must cache it
    while online; local_files_only=True keeps runtime inference offline.
    """
    path = Path(audio_path)
    if not path.is_file():
        raise SpeechError("Audio file does not exist.")
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise SpeechError("Speech support is not installed. Run project setup first.") from exc

    size = model_size or os.environ.get("GLASSES_WHISPER_MODEL", "base")
    cache_dir = Path(os.environ.get("GLASSES_MODEL_CACHE", Path(__file__).resolve().parents[2] / "models" / "whisper"))
    try:
        model = WhisperModel(
            size,
            device="cpu",
            compute_type="int8",
            download_root=str(cache_dir),
            local_files_only=True,
        )
        segments, info = model.transcribe(str(path), beam_size=3, vad_filter=True)
        text = " ".join(segment.text.strip() for segment in segments).strip()
    except Exception as exc:
        raise SpeechError(
            "Offline speech model is not cached or audio could not be processed. "
            "Cache the multilingual model during setup, then retry."
        ) from exc
    return {
        "text": text,
        "language": getattr(info, "language", None),
        "language_probability": getattr(info, "language_probability", None),
        "model": size,
        "offline": True,
    }
