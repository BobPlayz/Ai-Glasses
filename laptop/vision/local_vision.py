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


def _request_vision_answer(
    host: str,
    model: str,
    image_b64: str,
    prompt: str,
    *,
    attempt: int,
    image_bytes_count: int,
) -> str:
    """Make one local Ollama request and log safe diagnostics, never image data."""
    import logging
    import time

    logger = logging.getLogger(__name__)
    payload = {
        "model": model,
        "stream": False,
        "keep_alive": "5m",
        "messages": [{
            "role": "user",
            "content": prompt,
            "images": [image_b64],
        }],
        "options": {"temperature": 0.1, "num_ctx": 2048},
    }
    request = urllib.request.Request(
        host + "/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started = time.monotonic()
    status_code = 200
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            status_code = getattr(response, "status", 200)
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:400]
        logger.warning(
            "Vision request failed attempt=%s model=%s image_bytes=%s status=%s elapsed_ms=%s error=HTTPError",
            attempt, model, image_bytes_count, exc.code,
            int((time.monotonic() - started) * 1000),
        )
        raise VisionError(f"Local vision attempt {attempt} failed with HTTP {exc.code}: {detail}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        logger.warning(
            "Vision request failed attempt=%s model=%s image_bytes=%s status=%s elapsed_ms=%s error=%s",
            attempt, model, image_bytes_count, status_code,
            int((time.monotonic() - started) * 1000), type(exc).__name__,
        )
        raise VisionError(
            f"Local vision attempt {attempt} failed ({type(exc).__name__}: {exc}). "
            "Check that Ollama is running and try again."
        ) from exc
    except json.JSONDecodeError as exc:
        logger.warning(
            "Vision request failed attempt=%s model=%s image_bytes=%s status=%s elapsed_ms=%s error=JSONDecodeError",
            attempt, model, image_bytes_count, status_code,
            int((time.monotonic() - started) * 1000),
        )
        raise VisionError(f"Local vision attempt {attempt} returned invalid JSON.") from exc

    message = result.get("message", {}) if isinstance(result, dict) else {}
    answer = message.get("content", "").strip() if isinstance(message, dict) else ""
    logger.info(
        "Vision request attempt=%s model=%s image_bytes=%s status=%s elapsed_ms=%s content_nonempty=%s",
        attempt, model, image_bytes_count, status_code,
        int((time.monotonic() - started) * 1000), bool(answer),
    )
    return answer


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
    if len(question) > 500:
        raise VisionError("Vision question must be 500 characters or fewer.")

    # Decode and validate before OCR. Signatures alone are insufficient: reject
    # unsupported formats, multi-frame files, and pixel bombs before inference.
    try:
        from PIL import Image

        with Image.open(io.BytesIO(image_bytes)) as source:
            if source.format not in {"JPEG", "PNG", "WEBP", "BMP"}:
                raise VisionError("Only JPEG, PNG, WebP, and BMP images are supported.")
            if source.width < 1 or source.height < 1 or source.width * source.height > 20_000_000:
                raise VisionError("Image dimensions exceed the 20-megapixel safety limit.")
            if getattr(source, "n_frames", 1) != 1:
                raise VisionError("Animated or multi-frame images are not supported.")
            source.load()
            image = source.convert("RGB")
            image.thumbnail((1280, 1280))
            optimized = io.BytesIO()
            image.save(optimized, format="JPEG", quality=85, optimize=True)
            vision_image_bytes = optimized.getvalue()
    except VisionError:
        raise
    except Exception as exc:
        raise VisionError("Could not safely decode the captured image. Try a standard JPEG or PNG snapshot.") from exc

    # OCR runs only after the image has passed the byte, format, and pixel limits.
    ocr_text = extract_text_local(image_bytes)

    host = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
    from urllib.parse import urlsplit
    parsed = urlsplit(host)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise VisionError("Vision inference is restricted to the local Ollama service.")
    if parsed.username or parsed.password:
        raise VisionError("OLLAMA_HOST must not contain credentials.")
    model = os.environ.get("GLASSES_VISION_MODEL", "moondream:1.8b")
    image_b64 = base64.b64encode(vision_image_bytes).decode("ascii")

    answer = _request_vision_answer(
        host, model, image_b64, question,
        attempt=1, image_bytes_count=len(vision_image_bytes),
    )
    if not answer:
        # Some small local vision models return an empty message for a prompt.
        # Retry once with a simpler prompt; keep failure details if the retry fails.
        answer = _request_vision_answer(
            host, model, image_b64,
            "Describe this image briefly. Read visible text if possible.",
            attempt=2, image_bytes_count=len(vision_image_bytes),
        )
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
        raise VisionError(
            "The local vision model returned no description on either attempt. "
            "Check the local vision logs for safe per-attempt diagnostics and try again."
        )
    return {"answer": answer, "ocr_text": ocr_text, "model": model, "offline": True}
