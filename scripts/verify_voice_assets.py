from __future__ import annotations

import tempfile
import wave
from pathlib import Path

from piper import PiperVoice

ROOT = Path(__file__).resolve().parents[1]
VOICE_DIR = ROOT / "models" / "tts"
VOICES = ("en_GB-alan-medium", "te_IN-venkatesh-medium")


def main() -> int:
    for name in VOICES:
        model = VOICE_DIR / f"{name}.onnx"
        config = VOICE_DIR / f"{name}.onnx.json"
        if not model.is_file() or not config.is_file():
            raise SystemExit(f"Missing voice assets for {name}")
        voice = PiperVoice.load(str(model), config_path=str(config))
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp:
            output = Path(temp.name)
        try:
            with wave.open(str(output), "wb") as wav_file:
                voice.synthesize_wav("Ready.", wav_file)
            with wave.open(str(output), "rb") as wav_file:
                if wav_file.getnframes() <= 0:
                    raise SystemExit(f"Voice produced no audio: {name}")
        finally:
            output.unlink(missing_ok=True)
        print(f"PASS: {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
