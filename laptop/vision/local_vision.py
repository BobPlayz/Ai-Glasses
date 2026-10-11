from __future__ import annotations

import base64
import io
import json
import os
import shutil
import urllib.error
import urllib.request
from pathlib import Path


class VisionError(RuntimeError):
    pass


ROOT = Path(__file__).resolve().parents[2]
TESSDATA_DIR = ROOT / "models" / "tesseract" / "tessdata"


def extract_text_local(image_bytes: bytes) -> str:
    """Run local Tesseract OCR in English and Telugu when assets are available."""
    executable = shutil.which("tesseract")
    if not executable:
        for candidate in (
            Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
            Path(r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"),
        ):
            if candidate.is_file():
                executable = str(candidate)
                break
    if not executable:
        return ""

    try:
        from PIL import Image
        import pytesseract

        pytesseract.pytesseract.tesseract_cmd = executable
        with Image.open(io.BytesIO(image_bytes)) as source:
            image = source.convert("RGB")
            if image.width * image.height > 20_000_000:
                image.thumbnail((4000, 4000))
            languages = "eng+tel" if (TESSDATA_DIR / "tel.traineddata").is_file() else "eng"
            config = f"--tessdata-dir {TESSDATA_DIR}" if TESSDATA_DIR.is_dir() else ""
            text = pytesseract.image_to_string(image, lang=languages, config=config, timeout=12)
        return text.strip()[:6000]
    except Exception:
        return ""


def ask_image_local(image_bytes: bytes, question: str) -> dict:
    """Ask a local Ollama vision model about one explicitly captured image.

    This function does not capture images. Callers must verify the physical privacy
    switch and capture indicator before passing a camera frame here.
    """
    if not image_bytes:
        raise VisionError("No image bytes were supplied.")
    if len(image_bytes) > 8 * 1024 * 1024:
        raise VisionError("Image is larger than the 8 MB safety limit.")
    question = question.strip() or "Describe the main visible objects and any readable text."
    ocr_text = extract_text_local(image_bytes)

    # Phone cameras often send 12 MP+ frames. Keep OCR on the original image,
    # but give the vision model a bounded JPEG to reduce CPU time and memory use.
    try:
        from PIL import Image

        with Image.open(io.BytesIO(image_bytes)) as source:
            image = source.convert("RGB")
            image.thumbnail((1280, 1280))
            optimized = io.BytesIO()
            image.save(optimized, format="JPEG", quality=85, optimize=True)
            vision_image_bytes = optimized.getvalue()
    except Exception as exc:
        raise VisionError("Could not decode the captured image. Try another phone snapshot.") from exc

    host = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
    from urllib.parse import urlsplit
    parsed = urlsplit(host)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise VisionError("Vision inference is restricted to the local Ollama service.")
    if parsed.username or parsed.password:
        raise VisionError("OLLAMA_HOST must not contain credentials.")
    model = os.environ.get("GLASSES_VISION_MODEL", "moondream:1.8b")
    # Keep the vision prompt short. Moondream can return an empty message when
    # a long OCR transcript is appended to the image question; OCR is returned
    # separately to the caller instead of being fed back into vision inference.
    prompt = question
    payload = {
        "model": model,
        "stream": False,
        "keep_alive": "5m",
        "messages": [{
            "role": "user",
            "content": prompt,
            "images": [base64.b64encode(vision_image_bytes).decode("ascii")],
        }],
        "options": {"temperature": 0.1, "num_ctx": 2048},
    }
    request = urllib.request.Request(
        host + "/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:400]
        raise VisionError(f"Local vision model error HTTP {exc.code}: {detail}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise VisionError(f"Could not complete local vision request ({type(exc).__name__}: {exc}). Check that Ollama is running and try again.") from exc
    except json.JSONDecodeError as exc:
        raise VisionError("Local vision service returned invalid JSON.") from exc
    answer = result.get("message", {}).get("content", "").strip()
    if not answer:
        # Some small local vision models occasionally return an empty message
        # for longer prompts. Retry once with a simpler prompt before falling back.
        retry_payload = {
            "model": model,
            "stream": False,
            "keep_alive": "5m",
            "messages": [{
                "role": "user",
                "content": "Describe this image briefly. Read visible text if possible.",
                "images": [base64.b64encode(vision_image_bytes).decode("ascii")],
            }],
            "options": {"temperature": 0.1, "num_ctx": 2048},
        }
        retry_request = urllib.request.Request(
            host + "/api/chat",
            data=json.dumps(retry_payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(retry_request, timeout=180) as response:
                retry_result = json.loads(response.read().decode("utf-8"))
            answer = retry_result.get("message", {}).get("content", "").strip()
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError):
            answer = ""
    if not answer and ocr_text:
        answer = "I couldn't describe the image reliably. Offline OCR found this text: " + ocr_text
        return {
            "answer": answer,
            "ocr_text": ocr_text,
            "model": model,
            "offline": True,
            "vision_fallback": True,
        }
    if not answer:
        raise VisionError("The local vision model returned no description. Please try the image again.")
    return {"answer": answer, "ocr_text": ocr_text, "model": model, "offline": True}
