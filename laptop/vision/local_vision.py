from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request


class VisionError(RuntimeError):
    pass


def ask_image_local(image_bytes: bytes, question: str) -> dict:
    """Ask a local Ollama vision model about one explicitly captured image.

    This helper does not capture images or activate a camera. Callers must first
    verify the physical privacy switch and capture indicator through the device
    protocol before passing a frame here.
    """
    if not image_bytes:
        raise VisionError("No image bytes were supplied.")
    if len(image_bytes) > 8 * 1024 * 1024:
        raise VisionError("Image is larger than the 8 MB safety limit.")
    question = question.strip()
    if not question:
        question = "Describe the main visible objects and any readable text."
    host = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
    from urllib.parse import urlsplit
    parsed = urlsplit(host)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise VisionError("Vision inference is restricted to the local Ollama service.")
    model = os.environ.get("GLASSES_VISION_MODEL", "moondream:1.8b")
    payload = {
        "model": model,
        "stream": False,
        "keep_alive": "0",
        "messages": [{
            "role": "user",
            "content": question + " Answer in the language used by the user. If text is unclear, say so.",
            "images": [base64.b64encode(image_bytes).decode("ascii")],
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
        with urllib.request.urlopen(request, timeout=60) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:400]
        raise VisionError(f"Local vision model error HTTP {exc.code}: {detail}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise VisionError("Local vision service is unavailable or timed out.") from exc
    except json.JSONDecodeError as exc:
        raise VisionError("Local vision service returned invalid JSON.") from exc
    answer = result.get("message", {}).get("content", "").strip()
    if not answer:
        raise VisionError("Local vision model returned an empty answer.")
    return {"answer": answer, "model": model, "offline": True}
