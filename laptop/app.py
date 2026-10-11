from __future__ import annotations

import asyncio
import hmac
import json
import os
import re
import sqlite3
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import Depends, FastAPI, File, Header, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from laptop.assistant.ollama_client import OllamaError, ask_local, service_status
from laptop.memory.store import search_memories
from laptop.speech.speak import speak_local
from laptop.speech.transcribe import SpeechError, transcribe_audio_file
from laptop.vision.local_vision import VisionError, ask_image_local

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
TEMP_DIR = DATA_DIR / "temp"
DB_PATH = DATA_DIR / "memory.sqlite3"
PIN_PATH = ROOT / ".dashboard-pin"
DEVICE_TOKEN_PATH = ROOT / ".device-token"
WAKE_PHRASE_PATH = DATA_DIR / "wake-phrase.txt"
DATA_DIR.mkdir(parents=True, exist_ok=True)
TEMP_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="AI Glasses Local Dashboard", version="0.2.0")
_capture_lock = asyncio.Lock()
_capture_request: dict | None = None
_last_device_status: dict = {"connected": False}
_last_frame: dict | None = None
_dashboard_camera_enabled = False
_dashboard_microphone_enabled = False  # Explicit opt-in; device mic uploads are blocked by default.
_voice_armed = False
_voice_question_parts: list[str] = []
_voice_last_event: dict = {"state": "idle", "detail": "No device audio received yet."}
_last_indicator_on_at: str | None = None


def connect_db() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection



def recent_conversation_context(limit: int = 6) -> list[dict[str, str]]:
    """Return a small recent dialogue window for natural follow-up questions."""
    try:
        with connect_db() as db:
            rows = db.execute(
                "SELECT user_text, assistant_text FROM conversations ORDER BY id DESC LIMIT ?",
                (max(1, min(limit, 8)),),
            ).fetchall()
    except sqlite3.Error:
        return []
    history: list[dict[str, str]] = []
    for row in reversed(rows):
        history.append({"role": "user", "content": row["user_text"]})
        history.append({"role": "assistant", "content": row["assistant_text"]})
    return history


def init_db() -> None:
    with connect_db() as db:
        db.execute(
            """CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            )"""
        )
        db.execute(
            """CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_text TEXT NOT NULL,
                assistant_text TEXT NOT NULL,
                model TEXT NOT NULL,
                created_at TEXT NOT NULL
            )"""
        )


init_db()


class MemoryInput(BaseModel):
    content: Annotated[str, Field(min_length=1, max_length=1000)]


class AskInput(BaseModel):
    content: Annotated[str, Field(min_length=1, max_length=2000)]
    remember_summary: bool = False


class DeviceStatusInput(BaseModel):
    board: str = "ESP32-S3"
    connected: bool = True
    camera_enabled: bool = False
    privacy_switch_enabled: bool = False
    indicator_on: bool = False
    microphone_ready: bool = False
    firmware_version: str = "unknown"


class CaptureRequest(BaseModel):
    question: Annotated[str, Field(min_length=1, max_length=500)]


class WakePhraseInput(BaseModel):
    phrase: Annotated[str, Field(min_length=3, max_length=80)]


class CameraControlInput(BaseModel):
    enabled: bool


class MicrophoneControlInput(BaseModel):
    enabled: bool


def read_secret(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def dashboard_pin_required() -> bool:
    return os.environ.get("GLASSES_LAN_MODE", "0") == "1"


def verify_dashboard_pin(x_dashboard_pin: str | None = Header(default=None)) -> None:
    if not dashboard_pin_required():
        return
    expected = read_secret(PIN_PATH)
    if not expected:
        raise HTTPException(status_code=503, detail="LAN mode is blocked until setup creates .dashboard-pin.")
    if not x_dashboard_pin or not hmac.compare_digest(x_dashboard_pin, expected):
        raise HTTPException(status_code=401, detail="Dashboard PIN is missing or incorrect.")


def current_wake_phrase() -> str:
    try:
        phrase = WAKE_PHRASE_PATH.read_text(encoding="utf-8").strip()
    except OSError:
        phrase = ""
    return phrase or "hey glasses"


def normalize_speech(text: str) -> str:
    cleaned = []
    for character in text.casefold():
        category = unicodedata.category(character)
        if character.isspace() or category[0] in {"L", "M", "N"}:
            cleaned.append(character)
        else:
            cleaned.append(" ")
    return " ".join("".join(cleaned).split())


def is_visual_question(text: str) -> bool:
    normalized = normalize_speech(text)
    phrases = (
        "what am i looking at", "what am i seeing", "what is this", "what is in front of me",
        "describe what you see", "describe this", "read this", "read the text", "read this sign",
        "what does this say", "what is written here", "identify this", "look at this",
        "నేను ఏమి చూస్తున్నాను", "నేను ఏం చూస్తున్నాను", "ఇది ఏమిటి", "ఇది ఏంటి",
        "ఇది చదువు", "చదివి చెప్పు", "నా ముందు ఏముంది", "ఇక్కడ ఏముంది", "ఇందులో ఏముంది",
    )
    return any(phrase in normalized for phrase in phrases)


def short_speech_text(text: str, limit: int = 220) -> str:
    clean = " ".join(text.strip().split())
    if len(clean) <= limit:
        return clean
    sentences = re.split(r"(?<=[.!?।])\s+", clean)
    chosen = ""
    for sentence in sentences:
        candidate = (chosen + " " + sentence).strip()
        if len(candidate) > limit:
            break
        chosen = candidate
    if chosen:
        return chosen
    clipped = clean[:limit]
    return clipped.rsplit(" ", 1)[0] if " " in clipped else clipped


def verify_device_token(x_device_token: str | None = Header(default=None)) -> None:
    expected = read_secret(DEVICE_TOKEN_PATH)
    if not expected:
        raise HTTPException(status_code=503, detail="Device pairing token has not been generated by setup.")
    if not x_device_token or not hmac.compare_digest(x_device_token, expected):
        raise HTTPException(status_code=401, detail="Device pairing token is missing or incorrect.")


DashboardAuth = Annotated[None, Depends(verify_dashboard_pin)]
DeviceAuth = Annotated[None, Depends(verify_device_token)]


@app.get("/", response_class=HTMLResponse)
def dashboard() -> str:
    return DASHBOARD_HTML


@app.get("/api/status", dependencies=[Depends(verify_dashboard_pin)])
def status() -> dict:
    model_status = service_status()
    models = model_status["models"]
    device_fresh = bool(_last_device_status.get("connected")) and time.time() - _last_device_status.get("updated_at", 0) < 8
    return {
        "app": "running",
        "mode": "local-only",
        "language_model": ", ".join(models) if model_status["available"] and models else "Ollama unavailable or models not downloaded",
        "speech_recognition": "cached local Whisper; live voice requires the paired device microphone",
        "text_to_speech": "Offline male Piper neural English and Telugu voices (no API key or cloud service)",
        "vision_ocr": "local Tesseract English/Telugu OCR + Ollama vision model",
        "glasses_device": "connected" if device_fresh else "not connected",
        "camera": "capture allowed" if _dashboard_camera_enabled and device_fresh and _last_device_status.get("camera_enabled") and _last_device_status.get("privacy_switch_enabled") else "capture disabled / unverified",
        "dashboard_camera_enabled": _dashboard_camera_enabled,
        "microphone": ("enabled; local audio processing" if _dashboard_microphone_enabled else "disabled by dashboard") if _last_device_status.get("microphone_ready") and device_fresh else "not connected / unverified",
        "dashboard_microphone_enabled": _dashboard_microphone_enabled,
        "wake_phrase": current_wake_phrase(),
        "voice_state": _voice_last_event.get("state", "idle"),
        "voice_question": _voice_last_event.get("question", ""),
        "voice_answer": _voice_last_event.get("answer", ""),
        "voice_ocr_text": _voice_last_event.get("ocr_text", ""),
        "last_indicator_on_at": _last_indicator_on_at or "no capture indicator event yet",
        "privacy_indicator": ("on" if _last_device_status.get("indicator_on") else "off") if device_fresh else "unverified (device heartbeat stale)",
        "memory": "local SQLite enabled",
        "network_dashboard": "PIN protected" if dashboard_pin_required() else "localhost mode",
    }


@app.get("/api/memory", dependencies=[Depends(verify_dashboard_pin)])
def list_memories() -> dict:
    with connect_db() as db:
        rows = db.execute("SELECT id, content, created_at FROM memories ORDER BY id DESC LIMIT 100").fetchall()
    return {"items": [dict(row) for row in rows]}


@app.post("/api/memory", status_code=201, dependencies=[Depends(verify_dashboard_pin)])
def add_memory(payload: MemoryInput) -> dict:
    content = payload.content.strip()
    if not content:
        raise HTTPException(status_code=422, detail="Memory cannot be blank.")
    timestamp = datetime.now(timezone.utc).isoformat()
    with connect_db() as db:
        cursor = db.execute("INSERT INTO memories (content, created_at) VALUES (?, ?)", (content, timestamp))
        memory_id = cursor.lastrowid
    return {"id": memory_id, "content": content, "created_at": timestamp}


@app.delete("/api/memory/{memory_id}", dependencies=[Depends(verify_dashboard_pin)])
def delete_memory(memory_id: int) -> dict:
    with connect_db() as db:
        cursor = db.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Memory not found.")
    return {"deleted": memory_id}


@app.delete("/api/memory", dependencies=[Depends(verify_dashboard_pin)])
def clear_memories() -> dict:
    with connect_db() as db:
        db.execute("DELETE FROM memories")
        db.execute("DELETE FROM conversations")
    return {"cleared": True}


@app.get("/api/conversations", dependencies=[Depends(verify_dashboard_pin)])
def list_conversations() -> dict:
    with connect_db() as db:
        rows = db.execute(
            "SELECT id, user_text, assistant_text, model, created_at FROM conversations ORDER BY id DESC LIMIT 30"
        ).fetchall()
    return {"items": [dict(row) for row in rows]}


def save_conversation(user_text: str, assistant_text: str, model: str, remember_summary: bool) -> None:
    if not remember_summary:
        return
    timestamp = datetime.now(timezone.utc).isoformat()
    # Privacy-first default: do not persist full conversation transcripts.
    summary = f"Conversation summary: User asked: {user_text[:180]}. Assistant answered: {assistant_text[:320]}"
    with connect_db() as db:
        db.execute(
            "INSERT INTO memories (content, created_at) VALUES (?, ?)",
            (summary, timestamp),
        )


@app.post("/api/ask", dependencies=[Depends(verify_dashboard_pin)])
def ask(payload: AskInput) -> dict:
    question = payload.content.strip()
    memories = search_memories(DB_PATH, question)
    try:
        reply = ask_local(question, memories, recent_conversation_context())
    except OllamaError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    save_conversation(question, reply.text, reply.model, payload.remember_summary)
    return {
        "status": "ok",
        "answer": reply.text,
        "model": reply.model,
        "used_fallback": reply.used_fallback,
        "memory_notes_used": len(memories),
        "offline_inference": True,
    }


@app.post("/api/speech/transcribe", dependencies=[Depends(verify_dashboard_pin)])
async def transcribe_audio(file: UploadFile = File(...)) -> dict:
    allowed = {"audio/wav", "audio/x-wav", "audio/mpeg", "audio/mp4", "audio/webm", "audio/ogg", "application/octet-stream"}
    if file.content_type and file.content_type.lower() not in allowed:
        raise HTTPException(status_code=415, detail="Upload a WAV, MP3, M4A, WebM, or OGG audio file.")
    raw = await file.read(20 * 1024 * 1024 + 1)
    if not raw:
        raise HTTPException(status_code=400, detail="Audio file is empty.")
    if len(raw) > 20 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Audio file exceeds the 20 MB limit.")
    suffix = Path(file.filename or "recording.wav").suffix.lower()
    if suffix not in {".wav", ".mp3", ".m4a", ".mp4", ".webm", ".ogg", ".flac"}:
        suffix = ".wav"
    path = TEMP_DIR / f"{uuid4().hex}{suffix}"
    try:
        path.write_bytes(raw)
        result = await run_in_threadpool(transcribe_audio_file, path)
        return result
    except SpeechError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    finally:
        path.unlink(missing_ok=True)
        await file.close()


@app.get("/api/wake-phrase", dependencies=[Depends(verify_dashboard_pin)])
def get_wake_phrase() -> dict:
    return {"phrase": current_wake_phrase(), "default_is_placeholder": not WAKE_PHRASE_PATH.exists()}


@app.post("/api/wake-phrase", dependencies=[Depends(verify_dashboard_pin)])
def set_wake_phrase(payload: WakePhraseInput) -> dict:
    phrase = payload.phrase.strip()
    if not phrase or len(phrase.split()) > 8:
        raise HTTPException(status_code=422, detail="Wake phrase must contain 1 to 8 words.")
    WAKE_PHRASE_PATH.write_text(phrase, encoding="utf-8")
    return {"phrase": phrase, "saved_locally": True}


@app.post("/api/speech/speak", dependencies=[Depends(verify_dashboard_pin)])
def speak(payload: MemoryInput) -> dict:
    try:
        spoken_text = short_speech_text(payload.content)
        result = speak_local(spoken_text)
        return {**result, "spoken_text": spoken_text, "shortened_for_speech": spoken_text != payload.content.strip()}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/api/vision", dependencies=[Depends(verify_dashboard_pin)])
async def vision(question: str = "Describe the main objects and read visible text if possible.", file: UploadFile = File(...)) -> dict:
    if file.content_type and file.content_type.lower() not in {"image/jpeg", "image/png", "image/webp", "image/bmp", "application/octet-stream"}:
        raise HTTPException(status_code=415, detail="Upload a JPEG, PNG, WebP, or BMP image.")
    raw = await file.read(8 * 1024 * 1024 + 1)
    if not raw:
        raise HTTPException(status_code=400, detail="Image is empty.")
    if len(raw) > 8 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Image exceeds the 8 MB limit.")
    try:
        result = await run_in_threadpool(ask_image_local, raw, question)
        return result
    except VisionError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    finally:
        await file.close()


@app.post("/api/device/audio", dependencies=[Depends(verify_device_token)])
async def device_audio(request: Request) -> dict:
    global _voice_armed, _voice_last_event, _voice_question_parts
    if not _dashboard_microphone_enabled:
        raise HTTPException(status_code=403, detail="Device microphone is disabled in the dashboard.")
    raw = await request.body()
    if not raw:
        raise HTTPException(status_code=400, detail="Audio chunk is empty.")
    if len(raw) > 2 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Audio chunk exceeds 2 MiB.")
    if not raw.startswith(b"RIFF") or raw[8:12] != b"WAVE":
        raise HTTPException(status_code=415, detail="Device audio must be a WAV file.")
    path = TEMP_DIR / f"mic-{uuid4().hex}.wav"
    try:
        path.write_bytes(raw)
        result = await run_in_threadpool(transcribe_audio_file, path, "base")
    except SpeechError as exc:
        _voice_last_event = {"state": "speech_unavailable", "detail": str(exc)}
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    finally:
        path.unlink(missing_ok=True)

    # A user may revoke permission while a chunk is being transcribed. Discard it
    # rather than continuing the voice interaction after opt-out.
    if not _dashboard_microphone_enabled:
        _voice_armed = False
        _voice_question_parts = []
        _voice_last_event = {"state": "disabled", "detail": "Microphone permission was revoked while processing audio."}
        return {"state": "disabled", "transcript": "", "wake_detected": False}

    transcript = (result.get("text") or "").strip()
    if not transcript:
        if _voice_armed and _voice_question_parts:
            question = " ".join(_voice_question_parts).strip()
            _voice_question_parts = []
            _voice_armed = False
            _voice_last_event = {"state": "thinking", "detail": "Question captured. Running local inference."}
        else:
            _voice_last_event = {"state": "listening", "detail": "No speech detected in the latest audio chunk."}
            return {"state": "listening", "transcript": "", "wake_detected": False}

    else:
        normalized = normalize_speech(transcript)
        phrase = current_wake_phrase()
        normalized_phrase = normalize_speech(phrase)
        if not _voice_armed:
            if not normalized_phrase or normalized_phrase not in normalized:
                _voice_last_event = {"state": "listening", "detail": "Waiting for the configured wake phrase."}
                return {"state": "listening", "transcript": transcript, "wake_detected": False}
            phrase_pattern = r"[\W_]+".join(re.escape(part) for part in phrase.split())
            phrase_match = re.search(phrase_pattern, transcript, flags=re.IGNORECASE | re.UNICODE)
            suffix = transcript[phrase_match.end():].strip(" ,.!?;:") if phrase_match else ""
            _voice_armed = True
            _voice_question_parts = [suffix] if len(suffix.split()) >= 2 else []
            _voice_last_event = {"state": "awake", "detail": "Wake phrase detected. Listening until you pause."}
            return {"state": "awake", "transcript": transcript, "wake_detected": True}
        _voice_question_parts.append(transcript)
        _voice_last_event = {"state": "collecting", "detail": "Collecting question audio until a pause is detected."}
        return {"state": "collecting", "transcript": transcript, "wake_detected": False}

    if not question:
        _voice_last_event = {"state": "listening", "detail": "No question text was recognized."}
        return {"state": "listening", "transcript": "", "wake_detected": False}
    if is_visual_question(question):
        _voice_last_event = {
            "state": "capturing",
            "detail": "A visual question was detected. Requesting one frame under both privacy controls.",
            "question": question,
        }
        try:
            visual = await capture_frame_for_question(question)
            spoken_text = short_speech_text(visual["answer"])
            speech = await run_in_threadpool(speak_local, spoken_text)
            _voice_last_event = {
                "state": "answered_visual",
                "detail": f"Visual question answered using {visual['model']}.",
                "question": question,
                "answer": visual["answer"],
                "ocr_text": visual.get("ocr_text", ""),
            }
            return {
                "state": "answered_visual",
                "transcript": question,
                "answer": visual["answer"],
                "ocr_text": visual.get("ocr_text", ""),
                "model": visual["model"],
                "speech": speech,
                "offline": True,
            }
        except HTTPException as exc:
            spoken_text = short_speech_text(exc.detail)
            await run_in_threadpool(speak_local, spoken_text)
            _voice_last_event = {"state": "visual_unavailable", "detail": exc.detail, "question": question, "answer": exc.detail}
            return {"state": "visual_unavailable", "transcript": question, "answer": exc.detail, "offline": True}

    memories = search_memories(DB_PATH, question)
    try:
        reply = await run_in_threadpool(ask_local, question, memories, recent_conversation_context())
    except OllamaError as exc:
        _voice_last_event = {"state": "error", "detail": str(exc)}
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    save_conversation(question, reply.text, reply.model, False)
    spoken_text = short_speech_text(reply.text)
    speech = await run_in_threadpool(speak_local, spoken_text)
    _voice_last_event = {
        "state": "answered",
        "detail": f"Answered using {reply.model}.",
        "question": question,
        "answer": reply.text,
    }
    return {
        "state": "answered",
        "transcript": question,
        "answer": reply.text,
        "model": reply.model,
        "used_fallback": reply.used_fallback,
        "speech": speech,
        "offline": True,
    }


@app.post("/api/camera/control", dependencies=[Depends(verify_dashboard_pin)])
def camera_control(payload: CameraControlInput) -> dict:
    global _dashboard_camera_enabled, _capture_request
    _dashboard_camera_enabled = payload.enabled
    if not _dashboard_camera_enabled:
        _capture_request = None
    return {"dashboard_camera_enabled": _dashboard_camera_enabled}


@app.post("/api/microphone/control", dependencies=[Depends(verify_dashboard_pin)])
def microphone_control(payload: MicrophoneControlInput) -> dict:
    global _dashboard_microphone_enabled, _voice_armed, _voice_question_parts, _voice_last_event
    _dashboard_microphone_enabled = payload.enabled
    if not _dashboard_microphone_enabled:
        _voice_armed = False
        _voice_question_parts = []
        _voice_last_event = {"state": "disabled", "detail": "Device microphone disabled in dashboard."}
    else:
        _voice_last_event = {"state": "listening", "detail": "Device microphone enabled. Audio is sent to this laptop for local processing."}
    return {"dashboard_microphone_enabled": _dashboard_microphone_enabled}


@app.post("/api/device/status", dependencies=[Depends(verify_device_token)])
def device_status(payload: DeviceStatusInput) -> dict:
    global _last_device_status, _last_indicator_on_at
    # The board firmware must only report camera_enabled after checking its physical switch.
    _last_device_status = payload.model_dump()
    _last_device_status["updated_at"] = time.time()
    if payload.indicator_on:
        _last_indicator_on_at = datetime.now(timezone.utc).isoformat()
    return {"accepted": True}


@app.get("/api/device/command", dependencies=[Depends(verify_device_token)])
def device_command() -> dict:
    global _capture_request
    if _capture_request and _capture_request.get("expires_at", 0) < time.time():
        _capture_request = None
    return {"capture": _capture_request or None, "camera_allowed": _dashboard_camera_enabled, "microphone_allowed": _dashboard_microphone_enabled}


@app.post("/api/device/capture-result", dependencies=[Depends(verify_device_token)])
async def device_capture_result(request_id: str, file: UploadFile = File(...)) -> dict:
    global _capture_request, _last_frame
    if not _capture_request or request_id != _capture_request["id"]:
        raise HTTPException(status_code=409, detail="No matching capture request is active.")
    if not _last_device_status.get("privacy_switch_enabled") or not _last_device_status.get("indicator_on"):
        raise HTTPException(status_code=403, detail="Device status does not confirm privacy switch and indicator.")
    raw = await file.read(8 * 1024 * 1024 + 1)
    if not raw or len(raw) > 8 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Frame is empty or exceeds the 8 MB limit.")
    _last_frame = {"request_id": request_id, "bytes": raw, "created_at": time.time()}
    _capture_request = None
    await file.close()
    return {"accepted": True, "request_id": request_id}


async def capture_frame_for_question(question: str) -> dict:
    global _capture_request, _last_frame
    if not _dashboard_camera_enabled:
        raise HTTPException(status_code=403, detail="Enable dashboard camera control first.")
    if not _last_device_status.get("connected") or time.time() - _last_device_status.get("updated_at", 0) >= 8:
        raise HTTPException(status_code=503, detail="Glasses device is not connected.")
    if not _last_device_status.get("privacy_switch_enabled"):
        raise HTTPException(status_code=403, detail="Turn on the physical camera privacy switch first.")
    if _capture_request:
        raise HTTPException(status_code=409, detail="A capture request is already active.")
    request_id = uuid4().hex
    _last_frame = None
    _capture_request = {"id": request_id, "question": question, "expires_at": time.time() + 12}
    deadline = time.time() + 12
    while time.time() < deadline:
        if not _dashboard_camera_enabled:
            _capture_request = None
            raise HTTPException(status_code=403, detail="Camera control was disabled before capture completed.")
        if not _last_device_status.get("privacy_switch_enabled"):
            _capture_request = None
            raise HTTPException(status_code=403, detail="Physical camera privacy switch was turned off.")
        if _last_frame and _last_frame["request_id"] == request_id:
            frame = _last_frame["bytes"]
            _last_frame = None
            _capture_request = None
            try:
                result = await run_in_threadpool(ask_image_local, frame, question)
                return {"request_id": request_id, **result}
            except VisionError as exc:
                raise HTTPException(status_code=503, detail=str(exc)) from exc
        await asyncio.sleep(0.2)
    _capture_request = None
    raise HTTPException(status_code=504, detail="No frame arrived from the glasses within 12 seconds.")


@app.post("/api/device/capture", dependencies=[Depends(verify_dashboard_pin)])
async def request_device_capture(payload: CaptureRequest) -> dict:
    return await capture_frame_for_question(payload.question)


@app.get("/api/device/config", dependencies=[Depends(verify_device_token)])
def device_config() -> dict:
    return {
        "protocol_version": 1,
        "poll_ms": 300,
        "max_frame_bytes": 8 * 1024 * 1024,
        "privacy": "firmware must physically gate camera power/capture; dashboard state alone is insufficient",
    }


DASHBOARD_HTML = r"""
<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>J.A.R.V.I.S. | AI Glasses</title>
<style>
:root{color-scheme:dark;--bg:#03080e;--panel:#07131eeF;--cyan:#27eaff;--muted:#638092;--text:#c9e4ed;--gold:#ffc95c;--green:#63f5bd;--line:#087f91}
*{box-sizing:border-box}body{margin:0;min-height:100vh;background:#03080e;color:var(--text);font:13px/1.55 Consolas,'Courier New',monospace;letter-spacing:.07em}body:before{content:"";position:fixed;inset:0;pointer-events:none;background:linear-gradient(#12677813 1px,transparent 1px),linear-gradient(90deg,#12677813 1px,transparent 1px);background-size:36px 36px}body:after{content:"";position:fixed;inset:22% 0 auto;height:1px;background:linear-gradient(90deg,transparent,#00d9ed40,transparent);pointer-events:none}
.corner{position:fixed;width:45px;height:45px;border-color:var(--gold);z-index:5;pointer-events:none}.tl{top:17px;left:17px;border-top:2px solid;border-left:2px solid}.tr{top:17px;right:17px;border-top:2px solid;border-right:2px solid}.bl{bottom:17px;left:17px;border-bottom:2px solid;border-left:2px solid}.br{bottom:17px;right:17px;border-bottom:2px solid;border-right:2px solid}
main{max-width:1800px;margin:auto;min-height:100vh;padding:18px 2.1vw 100px;position:relative}.brand{text-align:center;margin:0 0 18px}.brand h1{margin:0;font-weight:400;font-size:clamp(24px,2.5vw,38px);letter-spacing:.65em;color:#a8e5ee;padding-left:.65em}.brand p{margin:3px 0 0;color:#1b7588;font-size:10px;letter-spacing:.4em}.layout{display:grid;grid-template-columns:minmax(220px,1fr) minmax(300px,1.55fr) minmax(280px,1.15fr);gap:15px;align-items:stretch}.side{display:flex;flex-direction:column;gap:12px;min-width:0}.panel{position:relative;min-width:0;border:1px solid var(--line);background:var(--panel);padding:13px 15px;box-shadow:inset 0 0 20px #00c9df05}.panel:before,.panel:after{content:"";position:absolute;width:11px;height:11px;pointer-events:none}.panel:before{top:-1px;left:-1px;border-top:2px solid #70f4ff;border-left:2px solid #70f4ff}.panel:after{bottom:-1px;right:-1px;border-bottom:2px solid #70f4ff;border-right:2px solid #70f4ff}.panel h2{margin:0 0 10px;padding-bottom:8px;border-bottom:1px solid #14586a;font-size:13px;font-weight:400;letter-spacing:.2em;color:#70eafa;text-transform:uppercase}.metric{display:grid;grid-template-columns:48px 1fr 38px;gap:8px;align-items:center;margin:11px 0;color:var(--muted);font-size:11px}.bar{height:13px;background:#142632}.bar i{display:block;height:100%;width:0;background:var(--gold);transition:width .4s}.clock{font-size:clamp(22px,2.1vw,31px);letter-spacing:.12em;color:#69eafa;margin-top:12px}.date{font-size:10px;color:#587a8a;letter-spacing:.15em}.tiny{font-size:10px;color:var(--muted);overflow-wrap:anywhere}.mono{white-space:pre-wrap;overflow-wrap:anywhere;color:#9bbac6}.panel button{margin:6px 5px 0 0}
button,input,textarea{font:inherit;letter-spacing:inherit}button{cursor:pointer;color:var(--cyan);background:#071923;border:1px solid #137b8b;padding:9px 12px;font-size:10px;text-transform:uppercase}button:hover{background:#0b2632;border-color:var(--cyan)}button:disabled{opacity:.45;cursor:wait}input,textarea{width:100%;background:#040c14;color:var(--text);border:1px solid #174653;padding:10px;outline:none}input:focus,textarea:focus{border-color:var(--cyan)}textarea{min-height:76px;resize:vertical}label{display:block;color:#82a9b8;font-size:10px;margin:11px 0 5px;text-transform:uppercase}
.center{display:flex;flex-direction:column;justify-content:center;align-items:center;min-width:0;min-height:570px}.reactor{width:min(34vw,455px);min-width:260px;aspect-ratio:1;position:relative;display:grid;place-items:center;perspective:900px}.reactorCanvas{position:absolute;inset:0;width:100%;height:100%;z-index:2;pointer-events:none}.reactor .ring,.reactor .core{opacity:.22}.reactor .core{opacity:.45}.reactor:before{content:"";position:absolute;inset:3%;border-radius:50%;border:1px solid #00c9dc55;box-shadow:0 0 45px #00b8d52a,inset 0 0 45px #00b8d51b;animation:pulse 3s ease-in-out infinite}.ring{position:absolute;border-radius:50%}.r1{inset:6%;border:7px dotted #12b8cc9c;animation:spin 34s linear infinite}.r2{inset:13%;border:11px dashed #00c9db85;animation:spin 24s linear infinite reverse}.r3{inset:21%;border:1px solid #16d7e4a0;box-shadow:0 0 25px #00d9ed21}.r4{inset:27%;border:2px solid #54f4ff8a;border-radius:40% 60% 55% 45%;animation:morph 9s ease-in-out infinite alternate}.r5{inset:34%;border:1px solid #54f4ff9a;border-radius:35% 65% 44% 56%;animation:morph 7s ease-in-out infinite alternate-reverse}.core{width:20%;aspect-ratio:1;border-radius:50%;background:radial-gradient(circle,#f2ffff 0 18%,#7bf8ff 20% 38%,#10d5e8 55%,#0b718c 75%,transparent 77%);box-shadow:0 0 22px #49f7ff,0 0 65px #00d9ed9c,0 0 130px #00b8d54a;z-index:2;animation:beat 2s ease-in-out infinite}.online{margin:14px 0 0;color:#67eafa;letter-spacing:.35em}.online:before{content:"";display:inline-block;width:6px;height:6px;border-radius:50%;background:var(--green);box-shadow:0 0 9px var(--green);margin-right:10px}.caption{font-size:10px;color:#286c7d;letter-spacing:.2em;text-align:center;margin-top:6px}
.transcript{min-height:250px;flex:0 0 39%}.transcriptText{white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.9;font-size:13px}.terminal{flex:1;min-height:270px;padding:0;overflow:hidden}.termbar{padding:8px 12px;background:#101b25;border-bottom:1px solid #125263;color:#74dbe8;font-size:11px}.dots{color:#ffbd2e;letter-spacing:.4em}.termbody{padding:12px;height:calc(100% - 35px);min-height:225px;overflow:auto;font-size:11px;white-space:pre-wrap;overflow-wrap:anywhere}.logline{margin:0 0 8px}.logtime{color:#647c8b}.gold{color:var(--gold)}
.extras{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin-top:14px}.extras .panel{padding:15px}.privacy{color:var(--gold)}.commandbar{position:fixed;z-index:8;left:2.1vw;right:2.1vw;bottom:12px;max-width:1740px;margin:auto;display:flex;align-items:center;gap:10px;border:1px solid #21cfe1;border-radius:17px;background:#030c14f5;box-shadow:0 0 25px #00d9ed10;padding:8px 14px}.prompt{color:#68f7ff;font-size:21px}.commandbar input{border:0;background:transparent;min-width:0;box-shadow:none!important;font-size:13px}.commandbar button{white-space:nowrap}.out{white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.7;margin-top:8px}.memitem{padding:8px 0;border-bottom:1px solid #16404d}
@keyframes spin{to{transform:rotate(360deg)}}@keyframes pulse{50%{opacity:.45;transform:scale(.97)}}@keyframes beat{50%{transform:scale(.92);filter:brightness(1.3)}}@keyframes morph{to{transform:rotate(140deg) scale(.92);border-radius:60% 40% 62% 38%}}
@media(max-width:1000px){.layout{grid-template-columns:minmax(190px,.8fr) minmax(260px,1.2fr)}.center{grid-column:2;grid-row:1;min-height:440px}.side.right{grid-column:1/-1;display:grid;grid-template-columns:1fr 1fr}.extras{grid-template-columns:repeat(2,minmax(0,1fr))}.reactor{width:min(46vw,380px)}}
@media(max-width:650px){main{padding:16px 10px 95px}.brand h1{font-size:23px;letter-spacing:.32em;padding-left:.32em}.brand p{font-size:8px;letter-spacing:.16em}.layout{display:flex;flex-direction:column}.center{order:0;min-height:320px}.side.left{order:1}.side.right{order:2;display:flex}.reactor{width:min(76vw,340px);min-width:225px}.extras{grid-template-columns:1fr}.transcript{min-height:160px;flex:auto}.terminal{min-height:230px}.commandbar{left:8px;right:8px;bottom:7px;padding:6px 8px;gap:5px}.commandbar input{font-size:11px}.commandbar button{padding:8px 7px;font-size:9px}.corner{width:22px;height:22px}.tl{top:5px;left:5px}.tr{top:5px;right:5px}.bl{bottom:5px;left:5px}.br{bottom:5px;right:5px}}
@media(prefers-reduced-motion:reduce){*{animation:none!important;scroll-behavior:auto!important;transition:none!important}}
.connection-row{display:grid;grid-template-columns:minmax(150px,1.3fr) minmax(110px,1fr) auto;align-items:center;gap:8px;padding:9px 0;border-bottom:1px solid #16404d}.connection-row:last-of-type{border-bottom:0}.connection-row button{white-space:nowrap}.connection-row .tiny{overflow-wrap:anywhere}@media(max-width:650px){.connection-row{grid-template-columns:1fr 1fr}.connection-row b{grid-column:1/-1}.connection-row button{white-space:normal}}</style></head><body>
<i class="corner tl"></i><i class="corner tr"></i><i class="corner bl"></i><i class="corner br"></i>
<main>
<header class="brand"><h1>J · A · R · V · I · S</h1><p>JUST A RATHER VERY INTELLIGENT SYSTEM</p></header>
<section id="pinPanel" class="panel" style="display:none;margin-bottom:14px"><h2>Dashboard PIN</h2><input id="pin" type="password" placeholder="Dashboard PIN"><button onclick="savePin()">Unlock</button><span id="pinMessage"></span></section>
<div class="layout">
<aside class="side left">
<section class="panel"><h2>System</h2>
<div class="metric"><span>CPU</span><div class="bar"><i id="cpuBar"></i></div><span id="cpuVal">--</span></div>
<div class="metric"><span>MEM</span><div class="bar"><i id="memBar"></i></div><span id="memVal">--</span></div>
<div class="metric"><span>AI</span><div class="bar"><i id="aiBar"></i></div><span id="aiVal">IDLE</span></div>
<div class="clock" id="clock">--:--:--</div><div class="date" id="dateLine">LOCAL SYSTEM TIME</div><div id="serviceLine" class="tiny" style="margin-top:10px">Checking local services...</div>
</section>
<section class="panel"><h2>Inbox</h2><div id="inboxText" class="mono">NOT CONNECTED<br>Optional Gmail integration not configured.</div><button onclick="logActivity('Inbox is not configured. No account data is being shown.')">Inspect inbox</button></section>
<section class="panel"><h2>GitHub</h2><div id="githubText" class="mono">AI GLASSES<br>Repository: BobPlayz/Ai-Glasses<br>Live GitHub stats not connected.</div><button onclick="window.open('https://github.com/BobPlayz/Ai-Glasses','_blank','noopener')">Open repository</button></section>
</aside>
<section class="center"><div class="reactor" aria-label="Animated 3D JARVIS reactor"><canvas id="reactorCanvas" class="reactorCanvas"></canvas><div class="ring r1"></div><div class="ring r2"></div><div class="ring r3"></div><div class="ring r4"></div><div class="ring r5"></div><div class="core"></div></div><div class="online" id="onlineState">INITIALIZING</div><div class="caption" id="modelCaption">LOCAL AI · PRIVATE BY DESIGN</div></section>
<aside class="side right">
<section class="panel transcript"><h2>Transcript</h2><div id="transcriptText" class="transcriptText">» Ready when you are. Type a question below.</div><div id="answerMeta" class="tiny" style="margin-top:12px"></div></section>
<section class="panel terminal"><div class="termbar"><span class="dots">● ● ●</span> &nbsp; jarvis://activity <span class="gold" style="float:right">● LIVE</span></div><div id="activity" class="termbody"><p class="logline"><span class="gold">$</span> JARVIS core initializing...</p></div></section>
</aside></div>
<section class="panel" id="connectionsPanel" style="margin-top:14px"><h2>Connections hub</h2><p class="tiny">Connect or disable each available path from one place. Device link status is detected from its recent Wi-Fi heartbeat; camera and device microphone permissions are controlled separately.</p>
<div class="connection-row"><b>Glasses ↔ laptop (Wi-Fi)</b><span id="glassesLinkState" class="tiny">Checking…</span><button onclick="refreshConnections()">Refresh link</button></div>
<div class="connection-row"><b>Glasses camera</b><span id="glassesCameraLinkState" class="tiny">Disabled</span><button id="connectionCameraButton" onclick="toggleCameraControl()">Enable camera</button></div>
<div class="connection-row"><b>Glasses microphone</b><span id="glassesMicrophoneLinkState" class="tiny">Disabled</span><button id="connectionMicrophoneButton" onclick="toggleMicrophoneControl()">Enable microphone</button></div>
<div class="connection-row"><b>Laptop microphone</b><span id="laptopMicrophoneLinkState" class="tiny">Disconnected</span><button id="laptopMicConnectButton" onclick="startMicTest()">Connect / record</button><button id="laptopMicDisconnectButton" onclick="disconnectLaptopMic()" disabled>Disconnect</button></div>
<div class="connection-row"><b>Offline voice output</b><span id="speakerLinkState" class="tiny">Ready to test</span><button onclick="testVoiceOutput()">Test speaker</button></div>
<div id="connectionHelp" class="tiny" style="margin-top:8px">The glasses connect over Wi-Fi in this firmware. USB is currently for power/programming, not a live data connection.</div></section>
<section class="extras">
<div class="panel"><h2>Visual systems</h2><p class="tiny">Image uploads are analyzed locally. Glasses capture needs explicit request, dashboard permission, and the physical privacy switch.</p><label for="visionQuestion">Visual question</label><textarea id="visionQuestion" placeholder="What am I looking at?"></textarea><label for="imageFile">Choose image</label><input id="imageFile" type="file" accept="image/jpeg,image/png,image/webp,image/bmp"><button onclick="askUploadedImage()">Analyze image</button><button onclick="askGlasses()">Capture from glasses</button><div id="visionAnswer" class="out"></div></div>
<div class="panel"><h2>Voice & wake phrase</h2><label for="wakePhrase">Wake phrase</label><input id="wakePhrase" maxlength="80" placeholder="hey glasses"><button onclick="saveWakePhrase()">Save phrase</button><div id="wakeStatus" class="tiny" style="margin-top:8px">Loading local setting...</div><label for="speakText">Speak text</label><textarea id="speakText" placeholder="Type a short phrase to test the voice..."></textarea><button onclick="speakText()">Speak offline</button><label for="audioFile">Transcribe audio file</label><input id="audioFile" type="file" accept="audio/*"><button onclick="transcribe()">Transcribe file locally</button><div style="margin-top:10px"><button id="recordButton" onclick="startMicTest()">Record laptop mic</button><button id="stopRecordButton" onclick="stopMicTest()" disabled>Stop & transcribe</button><span id="micTestState" class="tiny">Browser mic simulator: ready</span></div><div class="tiny">Laptop-only microphone test. Audio is sent to this laptop for local transcription and temporary files are deleted.</div><div id="speechAnswer" class="out"></div></div>
<div class="panel"><h2>Memory & privacy</h2><label for="memory">Save local memory</label><textarea id="memory" placeholder="A useful fact to remember..."></textarea><button onclick="saveMemory()">Save memory</button><button onclick="loadMemories()">Refresh</button><button onclick="clearMemory()">Clear all</button><div id="memories" class="out"></div><hr style="border:0;border-top:1px solid #16404d;margin:14px 0"><div class="tiny">Dashboard camera: <b id="cameraControlState">disabled</b></div><div class="tiny">Device microphone: <b id="microphoneControlState">disabled</b></div><button id="microphoneControlButton" onclick="toggleMicrophoneControl()">Enable device microphone</button><div class="tiny">Microphone uploads are blocked until you explicitly enable them here. Audio is processed locally on this laptop.</div><div class="tiny">Physical indicator: <b id="indicatorState">unverified</b></div><button id="cameraControlButton" onclick="toggleCameraControl()">Enable camera control</button><div id="privacyBadge" class="privacy tiny" style="margin-top:9px">CAMERA OFF / UNVERIFIED</div></div>
</section><div class="tiny" style="text-align:center;margin-top:14px">LOCAL-FIRST · NO CLOUD AI · CAMERA CAPTURE IS EXPLICITLY GATED</div>
</main>
<div class="commandbar"><span class="prompt">›</span><input id="command" placeholder="Type a question, then press Enter..." autocomplete="off"><button id="sendButton" onclick="sendCommand()">Send ↵</button><button onclick="speakAnswer()">Speak</button></div>
<script>
let dashboardPin=sessionStorage.getItem('glasses-pin')||'',latestAnswer='',cameraEnabled=false,microphoneEnabled=false,aiBusy=false;
function esc(s){return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
function logActivity(message){const el=document.getElementById('activity'),p=document.createElement('p');p.className='logline';p.innerHTML='<span class="logtime">'+esc(new Date().toLocaleTimeString())+'</span> <span class="gold">$</span> '+esc(message);el.appendChild(p);while(el.children.length>45)el.removeChild(el.firstChild);el.scrollTop=el.scrollHeight}
async function api(url,options){options=options||{};let headers=Object.assign({'X-Dashboard-Pin':dashboardPin},options.headers||{});if(!(options.body instanceof FormData)&&!headers['Content-Type'])headers['Content-Type']='application/json';options.headers=headers;let r=await fetch(url,options),d;try{d=await r.json()}catch{d={detail:'Unexpected server response'}}if(r.status===401){document.getElementById('pinPanel').style.display='block';throw new Error('Dashboard PIN required. Enter it above.')}if(!r.ok)throw new Error(d.detail||'Request failed');return d}
function savePin(){dashboardPin=document.getElementById('pin').value;sessionStorage.setItem('glasses-pin',dashboardPin);document.getElementById('pinMessage').textContent=' PIN stored for this tab.';loadStatus();loadMemories();loadWakePhrase()}
function setTranscript(q,a,meta){document.getElementById('transcriptText').textContent='» '+q+'\n\n'+a;document.getElementById('answerMeta').textContent=meta||''}
async function sendCommand(){let box=document.getElementById('command'),content=box.value.trim();if(!content||aiBusy)return;box.value='';aiBusy=true;document.getElementById('aiVal').textContent='BUSY';document.getElementById('aiBar').style.width='85%';document.getElementById('onlineState').textContent='THINKING';document.getElementById('sendButton').disabled=true;setTranscript(content,'Thinking locally...','LOCAL INFERENCE');logActivity('Question received: '+content.slice(0,90));try{let d=await api('/api/ask',{method:'POST',body:JSON.stringify({content,remember_summary:false})});latestAnswer=d.answer;setTranscript(content,d.answer,'MODEL '+d.model+(d.used_fallback?' · FALLBACK':'')+' · '+d.memory_notes_used+' MEMORY NOTES');document.getElementById('modelCaption').textContent='LOCAL AI · '+d.model;document.getElementById('onlineState').textContent='ONLINE';logActivity('Response ready using '+d.model);if(d.used_fallback)logActivity('Smaller fallback model used.')}catch(e){setTranscript(content,e.message,'REQUEST FAILED');document.getElementById('onlineState').textContent='CHECK SYSTEM';logActivity('Error: '+e.message)}finally{aiBusy=false;document.getElementById('aiVal').textContent='IDLE';document.getElementById('aiBar').style.width='12%';document.getElementById('sendButton').disabled=false}}
document.getElementById('command').addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();sendCommand()}});
function tickClock(){let d=new Date();document.getElementById('clock').textContent=d.toLocaleTimeString('en-GB',{hour12:false});document.getElementById('dateLine').textContent=d.toLocaleDateString('en-GB',{weekday:'short',day:'2-digit',month:'short',year:'numeric'}).toUpperCase()}
async function loadStatus(){try{let s=await api('/api/status');document.getElementById('onlineState').textContent='ONLINE';document.getElementById('serviceLine').textContent=s.language_model;document.getElementById('modelCaption').textContent='LOCAL AI · '+s.language_model;cameraEnabled=Boolean(s.dashboard_camera_enabled);microphoneEnabled=Boolean(s.dashboard_microphone_enabled);document.getElementById('cameraControlState').textContent=cameraEnabled?'enabled':'disabled';document.getElementById('microphoneControlState').textContent=microphoneEnabled?'enabled':'disabled';document.getElementById('microphoneControlButton').textContent=microphoneEnabled?'Disable device microphone':'Enable device microphone';document.getElementById('cameraControlButton').textContent=cameraEnabled?'Disable camera control':'Enable camera control';document.getElementById('indicatorState').textContent=s.privacy_indicator;let good=String(s.camera).includes('capture allowed')&&s.privacy_indicator==='on';document.getElementById('privacyBadge').textContent=good?'CAMERA CAPTURE ACTIVE':'CAMERA OFF / UNVERIFIED';document.getElementById('privacyBadge').style.color=good?'var(--green)':'var(--gold)';document.getElementById('inboxText').innerHTML='NOT CONNECTED<br>Optional Gmail integration not configured.';refreshConnections();logOnce('status','Local services checked. Camera '+(good?'active':'off or unverified')+'.')}catch(e){document.getElementById('onlineState').textContent='LOCAL ONLY';document.getElementById('serviceLine').textContent=e.message;logOnce('status-error','Status check: '+e.message)}}
const seen=new Set();function logOnce(k,m){if(seen.has(k))return;seen.add(k);logActivity(m)}
async function speakText(){let content=document.getElementById('speakText').value.trim();if(!content)return;latestAnswer=content;try{let d=await api('/api/speech/speak',{method:'POST',body:JSON.stringify({content})});document.getElementById('speechAnswer').textContent=d.spoken?'Spoken using '+(d.engine||'local speech')+(d.voice?' · '+d.voice:'')+'.':(d.message||d.reason||'Speech unavailable.');logActivity('Offline speech test requested.')}catch(e){document.getElementById('speechAnswer').textContent=e.message}}
async function speakAnswer(){if(!latestAnswer){logActivity('No answer available to speak.');return}document.getElementById('speakText').value=latestAnswer;await speakText()}
async function loadWakePhrase(){try{let d=await api('/api/wake-phrase');document.getElementById('wakePhrase').value=d.phrase;document.getElementById('wakeStatus').textContent=d.default_is_placeholder?'Placeholder only. Choose a phrase for your demo.':'Saved locally on this laptop.'}catch(e){document.getElementById('wakeStatus').textContent=e.message}}
async function saveWakePhrase(){let phrase=document.getElementById('wakePhrase').value.trim();if(!phrase)return;try{let d=await api('/api/wake-phrase',{method:'POST',body:JSON.stringify({phrase})});document.getElementById('wakeStatus').textContent='Saved locally: '+d.phrase;logActivity('Wake phrase saved.')}catch(e){document.getElementById('wakeStatus').textContent=e.message}}
let micRecorder=null,micStream=null,micChunks=[];
async function startMicTest(){try{if(!navigator.mediaDevices||!navigator.mediaDevices.getUserMedia)throw new Error('Microphone capture needs localhost or a secure browser context.');micStream=await navigator.mediaDevices.getUserMedia({audio:true});document.getElementById('laptopMicrophoneLinkState').textContent='Connected for this recording';document.getElementById('laptopMicConnectButton').disabled=true;document.getElementById('laptopMicDisconnectButton').disabled=false;micChunks=[];let mime=['audio/webm;codecs=opus','audio/webm','audio/mp4'].find(t=>MediaRecorder.isTypeSupported(t));micRecorder=new MediaRecorder(micStream,mime?{mimeType:mime}:undefined);micRecorder.ondataavailable=e=>{if(e.data&&e.data.size)micChunks.push(e.data)};micRecorder.onstop=async()=>{try{const blob=new Blob(micChunks,{type:micRecorder.mimeType||'audio/webm'});const ext=blob.type.includes('mp4')?'m4a':'webm';const form=new FormData();form.append('file',blob,'laptop-mic.'+ext);document.getElementById('micTestState').textContent='Transcribing locally...';const d=await api('/api/speech/transcribe',{method:'POST',headers:{'X-Dashboard-Pin':dashboardPin},body:form});document.getElementById('speechAnswer').textContent=(d.text||'(No speech recognized)')+'\\nLanguage: '+d.language+' · '+d.model;document.getElementById('command').value=d.text||'';document.getElementById('micTestState').textContent='Laptop mic test complete';logActivity('Laptop microphone simulator transcribed locally.')}catch(e){document.getElementById('micTestState').textContent=e.message}finally{if(micStream)micStream.getTracks().forEach(t=>t.stop());micStream=null;micRecorder=null;document.getElementById('recordButton').disabled=false;document.getElementById('stopRecordButton').disabled=true;document.getElementById('laptopMicConnectButton').disabled=false;document.getElementById('laptopMicDisconnectButton').disabled=true;document.getElementById('laptopMicrophoneLinkState').textContent='Disconnected'}};micRecorder.start();document.getElementById('recordButton').disabled=true;document.getElementById('stopRecordButton').disabled=false;document.getElementById('micTestState').textContent='Recording. Speak now, then press Stop & transcribe.'}catch(e){document.getElementById('micTestState').textContent=e.message}}
function stopMicTest(){if(micRecorder&&micRecorder.state!=='inactive')micRecorder.stop();document.getElementById('stopRecordButton').disabled=true}
async function transcribe(){let file=document.getElementById('audioFile').files[0];if(!file){alert('Choose an audio file first.');return}let form=new FormData();form.append('file',file);let out=document.getElementById('speechAnswer');out.textContent='Transcribing locally...';try{let d=await api('/api/speech/transcribe',{method:'POST',headers:{'X-Dashboard-Pin':dashboardPin},body:form});out.textContent=d.text+'\nLanguage: '+d.language+' · '+d.model;document.getElementById('command').value=d.text;logActivity('Audio transcription completed.')}catch(e){out.textContent=e.message}}
async function askUploadedImage(){let file=document.getElementById('imageFile').files[0];if(!file){alert('Choose an image first.');return}let form=new FormData();form.append('file',file);let q=document.getElementById('visionQuestion').value.trim()||'Describe the main objects and read visible text if possible.';let out=document.getElementById('visionAnswer');out.textContent='Analyzing locally...';try{let d=await api('/api/vision?question='+encodeURIComponent(q),{method:'POST',headers:{'X-Dashboard-Pin':dashboardPin},body:form});out.textContent=d.answer+'\nOCR: '+(d.ocr_text||'(no text detected)')+'\nModel: '+d.model;setTranscript(q,d.answer,'VISION · OFFLINE');logActivity('Chosen image analyzed locally.')}catch(e){out.textContent=e.message}}
async function askGlasses(){let question=document.getElementById('visionQuestion').value.trim();if(!question){alert('Enter a visual question first.');return}let out=document.getElementById('visionAnswer');out.textContent='Waiting for paired glasses and physical privacy switch...';try{let d=await api('/api/device/capture',{method:'POST',body:JSON.stringify({question})});out.textContent=d.answer+'\nOCR: '+(d.ocr_text||'(no text detected)')+'\nModel: '+d.model;setTranscript(question,d.answer,'GLASSES VISION · OFFLINE');logActivity('Requested one privacy-gated frame.')}catch(e){out.textContent=e.message;logActivity('Capture blocked: '+e.message)}}
async function refreshConnections(){try{const s=await api('/api/status');const connected=s.glasses_device==='connected';document.getElementById('glassesLinkState').textContent=connected?'Connected over Wi-Fi':'Disconnected / heartbeat stale';document.getElementById('glassesLinkState').style.color=connected?'var(--green)':'var(--gold)';document.getElementById('glassesCameraLinkState').textContent=s.dashboard_camera_enabled?'Permission enabled':'Permission disabled';document.getElementById('glassesMicrophoneLinkState').textContent=s.dashboard_microphone_enabled?'Permission enabled':'Permission disabled';document.getElementById('connectionCameraButton').textContent=s.dashboard_camera_enabled?'Disconnect camera permission':'Connect camera permission';document.getElementById('connectionMicrophoneButton').textContent=s.dashboard_microphone_enabled?'Disconnect microphone permission':'Connect microphone permission';document.getElementById('connectionHelp').textContent=connected?'Glasses link is active. Disable camera/microphone permissions separately when you want those parts disconnected.':'Check that the board is powered, on the same Wi-Fi, and configured with this laptop’s LAN IP.';}catch(e){document.getElementById('glassesLinkState').textContent='Unavailable: '+e.message}}
function disconnectLaptopMic(){if(micRecorder&&micRecorder.state!=='inactive'){micRecorder.onstop=null;micRecorder.stop()}if(micStream)micStream.getTracks().forEach(t=>t.stop());micStream=null;micRecorder=null;micChunks=[];document.getElementById('recordButton').disabled=false;document.getElementById('stopRecordButton').disabled=true;document.getElementById('laptopMicConnectButton').disabled=false;document.getElementById('laptopMicDisconnectButton').disabled=true;document.getElementById('laptopMicrophoneLinkState').textContent='Disconnected';document.getElementById('micTestState').textContent='Laptop microphone disconnected';logActivity('Laptop microphone disconnected; browser audio tracks stopped.')}
async function testVoiceOutput(){document.getElementById('speakText').value='AI glasses audio connection test.';document.getElementById('speakerLinkState').textContent='Testing local speech…';await speakText();document.getElementById('speakerLinkState').textContent=document.getElementById('speechAnswer').textContent.startsWith('Spoken using')?'Speech played through laptop output':'Speech test finished; check voice panel';}
async function toggleCameraControl(){try{let d=await api('/api/camera/control',{method:'POST',body:JSON.stringify({enabled:!cameraEnabled})});cameraEnabled=d.dashboard_camera_enabled;await loadStatus();refreshConnections();logActivity('Dashboard camera permission '+(cameraEnabled?'enabled':'disabled')+'.')}catch(e){alert(e.message)}}
async function toggleMicrophoneControl(){try{let d=await api('/api/microphone/control',{method:'POST',body:JSON.stringify({enabled:!microphoneEnabled})});microphoneEnabled=d.dashboard_microphone_enabled;await loadStatus();refreshConnections();logActivity('Device microphone '+(microphoneEnabled?'enabled':'disabled')+'.')}catch(e){alert(e.message)}}
async function saveMemory(){let content=document.getElementById('memory').value.trim();if(!content)return;try{await api('/api/memory',{method:'POST',body:JSON.stringify({content})});document.getElementById('memory').value='';await loadMemories();logActivity('Memory saved to local SQLite.')}catch(e){alert(e.message)}}
async function loadMemories(){try{let d=await api('/api/memory');document.getElementById('memories').innerHTML=d.items.length?d.items.slice(0,5).map(m=>'<div class="memitem">'+esc(m.content)+' <button onclick="deleteMemory('+m.id+')">Delete</button></div>').join(''):'<span class="tiny">No saved memories.</span>'}catch(e){document.getElementById('memories').textContent=e.message}}
async function deleteMemory(id){try{await api('/api/memory/'+id,{method:'DELETE'});await loadMemories()}catch(e){alert(e.message)}}
async function clearMemory(){if(!confirm('Delete all local memories and conversation summaries?'))return;try{await api('/api/memory',{method:'DELETE'});await loadMemories();logActivity('Local memory cleared.')}catch(e){alert(e.message)}}

const reactorCanvas=document.getElementById('reactorCanvas'),reactorCtx=reactorCanvas.getContext('2d');
let reactorW=0,reactorH=0,reactorFrame=0,reactorPointer={x:0,y:0},reactorMotion=1;
function resizeReactor(){const dpr=Math.min(window.devicePixelRatio||1,1.5),r=reactorCanvas.getBoundingClientRect();reactorW=r.width;reactorH=r.height;reactorCanvas.width=Math.round(r.width*dpr);reactorCanvas.height=Math.round(r.height*dpr);reactorCtx.setTransform(dpr,0,0,dpr,0,0)}
window.addEventListener('resize',resizeReactor);window.addEventListener('pointermove',e=>{reactorPointer.x=(e.clientX/window.innerWidth-.5)*.45;reactorPointer.y=(e.clientY/window.innerHeight-.5)*.35});document.addEventListener('visibilitychange',()=>{reactorMotion=document.hidden?0:1});
function drawReactor(){reactorFrame+=reactorMotion*.009;const c=reactorCtx,w=reactorW,h=reactorH,cx=w/2,cy=h/2,R=Math.min(w,h)*.34;c.clearRect(0,0,w,h);if(!w||!h){requestAnimationFrame(drawReactor);return}const yaw=reactorPointer.x+Math.sin(reactorFrame*.45)*.12,pitch=reactorPointer.y+Math.cos(reactorFrame*.3)*.08;
const project=(x,y,z)=>{const xx=x*Math.cos(yaw)-z*Math.sin(yaw),zz=x*Math.sin(yaw)+z*Math.cos(yaw),yy=y*Math.cos(pitch)-zz*Math.sin(pitch),zzz=y*Math.sin(pitch)+zz*Math.cos(pitch),scale=3.4/(3.4-zzz*.45);return{x:cx+xx*R*scale,y:cy+yy*R*scale,z:zzz,scale}};
c.save();c.globalCompositeOperation='lighter';
for(let ring=0;ring<4;ring++){const radius=R*(.56+ring*.145),tilt=(ring%2?-.8:.55)+pitch,rot=reactorFrame*(ring%2?-.65:.42);c.beginPath();for(let i=0;i<=180;i++){const a=i/180*Math.PI*2+rot,x=Math.cos(a)*radius/R,y=Math.sin(a)*radius/R*Math.cos(tilt),z=Math.sin(a)*radius/R*Math.sin(tilt),p=project(x,y,z);if(i===0)c.moveTo(p.x,p.y);else c.lineTo(p.x,p.y)}c.strokeStyle=ring%2?'rgba(39,234,255,.35)':'rgba(255,201,92,.48)';c.lineWidth=ring===2?1.5:1;c.stroke()}
const points=[];for(let i=0;i<150;i++){const y=1-2*(i+.5)/150,rad=Math.sqrt(1-y*y),a=i*2.399963+reactorFrame*.35;points.push(project(Math.cos(a)*rad*.83,y*.83,Math.sin(a)*rad*.83))}
points.sort((a,b)=>a.z-b.z);for(const p of points){const alpha=.25+((p.z+1)/2)*.7;c.beginPath();c.arc(p.x,p.y,Math.max(.6,1.5*p.scale),0,Math.PI*2);c.fillStyle='rgba(70,239,255,'+alpha+')';c.fill()}
const glow=c.createRadialGradient(cx,cy,1,cx,cy,R*.3);glow.addColorStop(0,'rgba(239,255,255,.95)');glow.addColorStop(.16,'rgba(64,246,255,.85)');glow.addColorStop(.55,'rgba(0,201,232,.22)');glow.addColorStop(1,'rgba(0,201,232,0)');c.fillStyle=glow;c.beginPath();c.arc(cx,cy,R*.32,0,Math.PI*2);c.fill();c.restore();requestAnimationFrame(drawReactor)}
resizeReactor();requestAnimationFrame(drawReactor);

loadStatus();loadMemories();loadWakePhrase();tickClock();setInterval(tickClock,1000);setInterval(loadStatus,10000);logActivity('JARVIS core online. Local services only.');
</script></body></html>
"""
