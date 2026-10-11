from __future__ import annotations

import base64
import io
import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from laptop.assistant.ollama_client import ask_local, service_status
from laptop.vision.local_vision import ask_image_local, extract_text_local


def make_test_image() -> bytes:
    image = Image.new("RGB", (640, 220), "white")
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype(r"C:\Windows\Fonts\arial.ttf", 54)
    except OSError:
        font = ImageFont.load_default()
    draw.rectangle((12, 12, 628, 208), outline="black", width=5)
    draw.text((35, 75), "AI GLASSES 42", fill="black", font=font)
    stream = io.BytesIO()
    image.save(stream, format="PNG")
    return stream.getvalue()


def main() -> int:
    status = service_status()
    if not status.get("available"):
        raise SystemExit("FAIL: Ollama local service is unavailable.")
    available = set(status.get("models", []))
    required = {"qwen2.5:1.5b", "qwen2.5:0.5b", "moondream:1.8b"}
    missing = required - available
    if missing:
        raise SystemExit("FAIL: missing local models: " + ", ".join(sorted(missing)))

    old_primary = os.environ.get("GLASSES_MODEL")
    old_fallback = os.environ.get("GLASSES_FALLBACK_MODEL")
    try:
        os.environ["GLASSES_MODEL"] = "qwen2.5:1.5b"
        os.environ["GLASSES_FALLBACK_MODEL"] = ""
        primary = ask_local("Reply with one short word: ready.")
        if not primary.text.strip():
            raise SystemExit("FAIL: primary model returned no answer.")
        print("PASS: primary local text model")

        os.environ["GLASSES_MODEL"] = "qwen2.5:0.5b"
        os.environ["GLASSES_FALLBACK_MODEL"] = ""
        fallback = ask_local("Reply with one short word: ready.")
        if not fallback.text.strip():
            raise SystemExit("FAIL: fallback model returned no answer.")
        print("PASS: fallback local text model")
    finally:
        if old_primary is None:
            os.environ.pop("GLASSES_MODEL", None)
        else:
            os.environ["GLASSES_MODEL"] = old_primary
        if old_fallback is None:
            os.environ.pop("GLASSES_FALLBACK_MODEL", None)
        else:
            os.environ["GLASSES_FALLBACK_MODEL"] = old_fallback

    image_bytes = make_test_image()
    vision = ask_image_local(image_bytes, "Describe the simple test image in one short sentence.")
    if not vision.get("answer", "").strip():
        raise SystemExit("FAIL: local vision model returned no answer.")
    print("PASS: local vision model")

    ocr = extract_text_local(image_bytes)
    if not ocr.strip():
        raise SystemExit("FAIL: local Tesseract OCR returned no text for the test image.")
    print("PASS: local OCR extracted text: " + " ".join(ocr.split())[:80])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
