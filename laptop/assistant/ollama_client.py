from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from urllib.parse import urlsplit


@dataclass
class ModelReply:
    text: str
    model: str
    used_fallback: bool = False


class OllamaError(RuntimeError):
    pass


def _ollama_url(path: str) -> str:
    # Never accept a remote host: all inference must remain on this machine.
    host = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
    parsed = urlsplit(host)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise OllamaError("OLLAMA_HOST must point to localhost for offline privacy.")
    if parsed.username or parsed.password:
        raise OllamaError("OLLAMA_HOST must not contain credentials.")
    return host + path


def _post_json(path: str, payload: dict, timeout: float) -> dict:
    request = urllib.request.Request(
        _ollama_url(path),
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise OllamaError(f"Local model service returned HTTP {exc.code}: {detail}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise OllamaError(
            "Local Ollama service is unavailable. Start Ollama and download the configured model first."
        ) from exc
    except json.JSONDecodeError as exc:
        raise OllamaError("Local model service returned invalid JSON.") from exc
    return result


def service_status(timeout: float = 2.0) -> dict:
    try:
        request = urllib.request.Request(_ollama_url("/api/tags"), method="GET")
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
        return {"available": True, "models": [m.get("name", "") for m in data.get("models", [])]}
    except Exception:
        return {"available": False, "models": []}


def ask_local(
    question: str,
    memories: list[str] | None = None,
    history: list[dict[str, str]] | None = None,
) -> ModelReply:
    question = question.strip()
    if not question:
        raise OllamaError("Enter a question first.")

    primary = os.environ.get("GLASSES_MODEL", "qwen2.5:1.5b")
    fallback = os.environ.get("GLASSES_FALLBACK_MODEL", "qwen2.5:0.5b")
    timeout = float(os.environ.get("GLASSES_MODEL_TIMEOUT", "45"))
    memory_lines = "\n".join(f"- {item[:300]}" for item in (memories or [])[:8])
    system = (
        "You are a capable, calm, JARVIS-inspired assistant running privately on smart glasses. "
        "Sound natural and conversational, not like a helpdesk or a long essay. "
        "Answer directly first; usually use 1-4 short sentences unless the user asks for detail. "
        "Use the language the user speaks, including natural everyday Andhra Telugu for Telugu input. "
        "Understand follow-up questions using the recent conversation context. "
        "Do not repeat greetings, narrate your reasoning, or over-explain simple answers. "
        "Never claim to see an image unless image content is explicitly provided. "
        "Never claim an action, device state, or live fact that has not been verified. "
        "These are relevant user-approved local memory notes:\\n"
        + (memory_lines or "(no relevant saved notes)")
    )

    def run(model: str) -> str:
        data = _post_json(
            "/api/chat",
            {
                "model": model,
                "stream": False,
                "keep_alive": "10m",
                "messages": [
                    {"role": "system", "content": system},
                    *[
                        {"role": item["role"], "content": item["content"][:1200]}
                        for item in (history or [])[-8:]
                        if item.get("role") in {"user", "assistant"} and item.get("content")
                    ],
                    {"role": "user", "content": question},
                ],
                "options": {"temperature": 0.45, "num_ctx": 3072, "num_predict": 180},
            },
            timeout,
        )
        answer = data.get("message", {}).get("content", "").strip()
        if not answer:
            raise OllamaError("The local model returned an empty answer.")
        return answer

    try:
        return ModelReply(text=run(primary), model=primary)
    except OllamaError as primary_error:
        if fallback and fallback != primary:
            try:
                return ModelReply(text=run(fallback), model=fallback, used_fallback=True)
            except OllamaError:
                pass
        raise OllamaError(str(primary_error)) from primary_error
