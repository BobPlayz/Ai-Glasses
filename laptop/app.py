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
_voice_armed = False
_voice_question_parts: list[str] = []
_voice_last_event: dict = {"state": "idle", "detail": "No device audio received yet."}
_last_indicator_on_at: str | None = None


def connect_db() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


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
        "text_to_speech": "cached Piper neural English/Telugu voices; Windows SAPI/eSpeak fallback",
        "vision_ocr": "local Tesseract English/Telugu OCR + Ollama vision model",
        "glasses_device": "connected" if device_fresh else "not connected",
        "camera": "capture allowed" if _dashboard_camera_enabled and device_fresh and _last_device_status.get("camera_enabled") and _last_device_status.get("privacy_switch_enabled") else "capture disabled / unverified",
        "dashboard_camera_enabled": _dashboard_camera_enabled,
        "microphone": "streaming local audio" if _last_device_status.get("microphone_ready") and time.time() - _last_device_status.get("updated_at", 0) < 8 else "not connected",
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
        reply = ask_local(question, memories)
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
    global _voice_armed, _voice_last_event
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

    global _voice_question_parts
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
        reply = await run_in_threadpool(ask_local, question, memories)
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
    return {"capture": _capture_request or None, "camera_allowed": _dashboard_camera_enabled}


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
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>AI Glasses | Local Control</title>
<style>
:root{color-scheme:dark;--bg:#07090e;--panel:rgba(15,20,31,.88);--panel2:#111827;--line:#263144;--cyan:#8be9fd;--blue:#77aaff;--muted:#9ba9bd;--text:#f3f6fc;--warn:#ffce76;--green:#7ef0bb;--radius:22px}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:radial-gradient(ellipse at 12% -8%,rgba(40,107,151,.28),transparent 36%),radial-gradient(ellipse at 95% 8%,rgba(83,67,146,.18),transparent 30%),var(--bg);color:var(--text);font:15px/1.6 Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif;letter-spacing:.005em}
body:before{content:"";position:fixed;inset:0;pointer-events:none;opacity:.13;background-image:linear-gradient(rgba(130,180,220,.07) 1px,transparent 1px),linear-gradient(90deg,rgba(130,180,220,.07) 1px,transparent 1px);background-size:42px 42px;mask-image:linear-gradient(to bottom,black,transparent 85%)}
main{position:relative;max-width:1440px;margin:auto;padding:34px clamp(16px,3vw,44px) 72px}.eyebrow{color:var(--cyan);letter-spacing:.22em;text-transform:uppercase;font-size:.7rem;font-weight:800}
h1{font-size:clamp(2.6rem,6vw,5rem);line-height:.98;letter-spacing:-.065em;margin:.55rem 0 1rem;font-weight:780}h2{font-size:1rem;letter-spacing:.01em;margin:0 0 14px;font-weight:750}.sub{color:var(--muted);max-width:800px;margin:.3rem 0 1.2rem}
.grid{display:grid;grid-template-columns:repeat(12,minmax(0,1fr));gap:16px;margin:26px 0}.grid>.card{grid-column:span 6;min-width:0}.grid>.card:first-child,.grid>.card:nth-child(2){grid-column:span 6}.card{position:relative;background:linear-gradient(145deg,rgba(19,27,42,.96),rgba(11,15,24,.96));border:1px solid rgba(126,157,194,.19);border-radius:var(--radius);padding:clamp(18px,2vw,28px);box-shadow:0 22px 60px rgba(0,0,0,.22);backdrop-filter:blur(18px);transition:border-color .2s,transform .2s}.card:hover{border-color:rgba(139,233,253,.38)}.card:focus-within{border-color:rgba(139,233,253,.5)}
.kv{display:flex;justify-content:space-between;gap:16px;padding:9px 0;border-bottom:1px solid rgba(130,155,190,.12)}.kv span:first-child{color:var(--muted);text-transform:capitalize}.kv span:last-child{text-align:right;overflow-wrap:anywhere;max-width:58%}
label{display:block;color:#bdc9d9;margin:15px 0 7px;font-size:.88rem;font-weight:600}textarea,input:not([type=checkbox]),input[type=file]{font:inherit;border-radius:13px;border:1px solid #303b50;padding:13px 14px;width:100%;background:rgba(5,9,16,.72);color:var(--text);outline:none;transition:border-color .18s,box-shadow .18s}textarea{min-height:104px;resize:vertical}textarea:focus,input:focus{border-color:var(--cyan);box-shadow:0 0 0 3px rgba(139,233,253,.09)}input[type=checkbox]{accent-color:#8be9fd}
button{font:inherit;font-size:.88rem;font-weight:700;background:linear-gradient(135deg,#b0f3ff,#74c8ee);color:#07121c;cursor:pointer;border:1px solid transparent;border-radius:12px;padding:11px 16px;margin:9px 5px 0 0;transition:transform .15s,filter .15s,border-color .15s}button:hover{filter:brightness(1.08);transform:translateY(-1px)}button:active{transform:translateY(0)}button.secondary{background:#151e2d;color:#e3edf9;border-color:#303d53}button.danger{background:#321d29;color:#ffc6d4;border-color:#704050}button:disabled{opacity:.5;cursor:not-allowed;transform:none}
.note{border:1px solid rgba(139,233,253,.2);border-left:3px solid var(--cyan);padding:13px 15px;background:rgba(16,39,52,.42);color:#c8e4f1;border-radius:0 13px 13px 0}.out{white-space:pre-wrap;overflow-wrap:anywhere;padding:14px 0;line-height:1.75}.item{border:1px solid #2b374a;border-radius:13px;padding:13px;margin:10px 0;background:rgba(6,10,17,.45);overflow-wrap:anywhere}.item small,.footer{color:var(--muted)}.footer{font-size:.82rem;margin-top:28px;border-top:1px solid #202b3c;padding-top:18px}.privacy{display:inline-flex;align-items:center;gap:8px;color:var(--warn);font-size:.75rem;font-weight:800;letter-spacing:.07em;border:1px solid rgba(255,206,118,.25);border-radius:999px;padding:8px 12px;background:rgba(255,206,118,.06)}.privacy.on{color:var(--green);border-color:rgba(126,240,187,.3);background:rgba(126,240,187,.06)}.file{font-size:.9rem}.topline{display:flex;justify-content:space-between;gap:16px;flex-wrap:wrap;align-items:center}.topline h1{margin-bottom:.35rem}
@media(min-width:1000px){.grid>.card:first-child{grid-column:span 5}.grid>.card:nth-child(2){grid-column:span 7}.grid>.card:nth-child(3),.grid>.card:nth-child(4){grid-column:span 6}.grid>.card:nth-child(5),.grid>.card:nth-child(6){grid-column:span 6}}
@media(max-width:720px){main{padding:24px 13px 48px}.grid{grid-template-columns:1fr;gap:12px;margin-top:18px}.grid>.card,.grid>.card:first-child,.grid>.card:nth-child(2),.grid>.card:nth-child(3),.grid>.card:nth-child(4),.grid>.card:nth-child(5),.grid>.card:nth-child(6){grid-column:1}.card{border-radius:18px;padding:18px}.topline{align-items:flex-start;flex-direction:column}.kv{gap:8px}.kv span:last-child{max-width:60%}}
</style></head>
<body><main>
<div class="eyebrow">LOCAL-FIRST · WINDOWS HOST</div>
<div class="topline"><h1>AI <span style="color:var(--cyan)">Glasses</span></h1><span id="privacyBadge" class="privacy">● CAMERA STATE UNVERIFIED</span></div>
<p class="sub">Offline assistant control room. Text AI, saved memory, speech-file transcription, and explicit image questions use local model services. The dashboard never silently turns on a camera.</p>
<section class="card" id="pinPanel" style="display:none"><h2>Dashboard PIN</h2><p class="sub">LAN mode is enabled. Enter the local PIN created by setup. It is kept only in this browser tab.</p><input id="pin" type="password" autocomplete="current-password" placeholder="Dashboard PIN"><button onclick="savePin()">Unlock dashboard</button><p id="pinMessage" role="status"></p></section>
<div class="grid">
<section class="card"><h2>System status</h2><div id="status">Checking local services...</div><button class="secondary" onclick="loadStatus()">Refresh status</button></section>
<section class="card"><h2>Ask the local AI</h2><p class="sub">Uses local Ollama. Primary model: qwen2.5:1.5b; smaller fallback: qwen2.5:0.5b.</p><label for="question">Question</label><textarea id="question" placeholder="Ask in English or Telugu..."></textarea><label><input type="checkbox" id="rememberSummary" style="width:auto"> Save a short summary to memory</label><button id="askButton" onclick="ask()">Ask locally</button><button class="secondary" onclick="speakAnswer()">Speak latest answer</button><div id="answer" class="out" role="status"></div></section>
<section class="card"><h2>Visual question</h2><div class="note">Camera use must be requested. For a live glasses capture, the paired device must report its physical privacy switch and indicator as active. You can also upload a chosen image for testing.</div><label for="visionQuestion">What do you want to know?</label><textarea id="visionQuestion" placeholder="Read the sign and explain what it says."></textarea><label for="imageFile">Choose image for a local test</label><input class="file" id="imageFile" type="file" accept="image/jpeg,image/png,image/webp,image/bmp"><button onclick="askUploadedImage()">Analyze chosen image</button><button class="secondary" onclick="askGlasses()">Capture from paired glasses</button><div id="visionAnswer" class="out" role="status"></div></section>
<section class="card"><h2>Wake phrase and speech</h2><p class="sub">The device mic sends short audio chunks over your private LAN. Audio is transcribed locally and temporary files are deleted after processing.</p><label for="wakePhrase">Your custom wake phrase</label><input id="wakePhrase" maxlength="80" placeholder="Choose your own phrase later"><button onclick="saveWakePhrase()">Save wake phrase</button><p id="wakeStatus" class="sub">Default placeholder: hey glasses</p><label for="audioFile">Audio file test</label><input class="file" id="audioFile" type="file" accept="audio/*"><button onclick="transcribe()">Transcribe locally</button><button class="secondary" onclick="speakText()">Speak text offline</button><label for="speakText">Text to speak</label><textarea id="speakText" placeholder="Short answer in English or Telugu..."></textarea><div id="speechAnswer" class="out" role="status"></div></section>
<section class="card"><h2>Local memory</h2><p class="sub">Useful facts and optional conversation summaries. Stored in SQLite on this laptop.</p><label for="memory">Memory</label><textarea id="memory" placeholder="A useful fact to remember..."></textarea><button onclick="saveMemory()">Save</button><button class="secondary" onclick="loadMemories()">Refresh</button><button class="danger" onclick="clearMemory()">Clear all memory and summaries</button><div id="memories" aria-live="polite"></div></section>
<section class="card"><h2>Privacy and device</h2><div class="kv"><span>Physical camera switch</span><span>Device-reported only</span></div><div class="kv"><span>Dashboard camera control</span><span id="cameraControlState">Disabled</span></div><button id="cameraControlButton" onclick="toggleCameraControl()">Enable dashboard camera control</button><div class="kv"><span>Camera indicator</span><span id="indicatorState">Unverified</span></div><div class="kv"><span>Capture behavior</span><span>Only after visual request</span></div><div class="kv"><span>LAN dashboard</span><span>PIN protected when enabled</span></div><p class="sub">Both the dashboard control and physical switch must allow capture. Firmware refuses captures when the switch is off and lights the indicator during capture.</p></section>
</div>
<p class="footer">Local-first privacy: no cloud AI calls. Do not expose the dashboard to a shared or public network. Device pairing and camera controls require a selected, programmed board.</p>
</main>
<script>
let dashboardPin=sessionStorage.getItem('glasses-pin')||'';
let latestAnswer='';
let cameraEnabled=false;
async function api(url,options){options=options||{};let headers=Object.assign({'X-Dashboard-Pin':dashboardPin},options.headers||{});if(!(options.body instanceof FormData)&&!headers['Content-Type'])headers['Content-Type']='application/json';options.headers=headers;let r=await fetch(url,options);let d;try{d=await r.json()}catch{d={detail:'Unexpected server response'}}if(r.status===401){document.getElementById('pinPanel').style.display='block';throw new Error('Enter the dashboard PIN.')}if(!r.ok)throw new Error(d.detail||'Request failed');return d}
function esc(s){return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
function savePin(){dashboardPin=document.getElementById('pin').value;sessionStorage.setItem('glasses-pin',dashboardPin);loadStatus().then(()=>{document.getElementById('pinPanel').style.display='none';loadMemories()}).catch(e=>document.getElementById('pinMessage').textContent=e.message)}
async function loadStatus(){try{let s=await api('/api/status');document.getElementById('status').innerHTML=Object.entries(s).map(([k,v])=>'<div class="kv"><span>'+esc(k.replace(/_/g,' '))+'</span><span>'+esc(v)+'</span></div>').join('');cameraEnabled=Boolean(s.dashboard_camera_enabled);document.getElementById('cameraControlState').textContent=cameraEnabled?'Enabled':'Disabled';document.getElementById('cameraControlButton').textContent=cameraEnabled?'Disable dashboard camera control':'Enable dashboard camera control';let good=String(s.camera).includes('capture allowed')&&s.privacy_indicator==='on';document.getElementById('privacyBadge').textContent=good?'● CAMERA CAPTURE ACTIVE':'● CAMERA STATE: OFF / UNVERIFIED';document.getElementById('privacyBadge').className='privacy'+(good?' on':'');document.getElementById('indicatorState').textContent=s.privacy_indicator}catch(e){document.getElementById('status').textContent=e.message;if(e.message.includes('PIN'))document.getElementById('pinPanel').style.display='block'}}
async function loadMemories(){try{let d=await api('/api/memory');document.getElementById('memories').innerHTML=d.items.length?d.items.map(m=>'<div class="item">'+esc(m.content)+'<br><small>'+esc(new Date(m.created_at).toLocaleString())+'</small> <button class="secondary" onclick="deleteMemory('+m.id+')">Delete</button></div>').join(''):'<p class="sub">No saved memories.</p>'}catch(e){document.getElementById('memories').textContent=e.message}}
async function saveMemory(){let content=document.getElementById('memory').value.trim();if(!content)return;try{await api('/api/memory',{method:'POST',body:JSON.stringify({content})});document.getElementById('memory').value='';await loadMemories()}catch(e){alert(e.message)}}
async function deleteMemory(id){try{await api('/api/memory/'+id,{method:'DELETE'});await loadMemories()}catch(e){alert(e.message)}}
async function clearMemory(){if(!confirm('Delete all saved memories and conversation summaries from this laptop?'))return;try{await api('/api/memory',{method:'DELETE'});await loadMemories()}catch(e){alert(e.message)}}
async function ask(){let content=document.getElementById('question').value.trim();if(!content)return;let out=document.getElementById('answer');out.textContent='Thinking locally...';document.getElementById('askButton').disabled=true;try{let d=await api('/api/ask',{method:'POST',body:JSON.stringify({content,remember_summary:document.getElementById('rememberSummary').checked})});latestAnswer=d.answer;out.textContent=d.answer+'\n\nModel: '+d.model+(d.used_fallback?' (fallback)':'')+' · memory notes: '+d.memory_notes_used}catch(e){out.textContent=e.message}finally{document.getElementById('askButton').disabled=false}}
async function speakAnswer(){if(!latestAnswer){alert('Ask a question first.');return}try{let d=await api('/api/speech/speak',{method:'POST',body:JSON.stringify({content:latestAnswer})});document.getElementById('speechAnswer').textContent=d.spoken?'Spoken using '+(d.engine||'local speech')+(d.voice?' ('+d.voice+')':'')+'.':(d.message||'Speech unavailable; answer remains visible.')}catch(e){document.getElementById('speechAnswer').textContent=e.message}}
async function speakText(){let content=document.getElementById('speakText').value.trim();if(!content)return;try{let d=await api('/api/speech/speak',{method:'POST',body:JSON.stringify({content})});document.getElementById('speechAnswer').textContent=d.spoken?'Spoken using '+(d.engine||'local speech')+(d.voice?' ('+d.voice+')':'')+'.':(d.message||d.reason)}catch(e){document.getElementById('speechAnswer').textContent=e.message}}
async function loadWakePhrase(){try{let d=await api('/api/wake-phrase');document.getElementById('wakePhrase').value=d.phrase;document.getElementById('wakeStatus').textContent=d.default_is_placeholder?'Placeholder only. Replace it with your chosen phrase before the final demo.':'Saved locally on this laptop.'}catch(e){document.getElementById('wakeStatus').textContent=e.message}}
async function saveWakePhrase(){let phrase=document.getElementById('wakePhrase').value.trim();if(!phrase)return;try{let d=await api('/api/wake-phrase',{method:'POST',body:JSON.stringify({phrase})});document.getElementById('wakeStatus').textContent='Saved locally: '+d.phrase}catch(e){document.getElementById('wakeStatus').textContent=e.message}}
async function transcribe(){let file=document.getElementById('audioFile').files[0];if(!file){alert('Choose an audio file first.');return}let form=new FormData();form.append('file',file);let out=document.getElementById('speechAnswer');out.textContent='Transcribing with the cached local model...';try{let d=await api('/api/speech/transcribe',{method:'POST',headers:{'X-Dashboard-Pin':dashboardPin},body:form});out.textContent=d.text+'\nLanguage: '+d.language+' · model: '+d.model;document.getElementById('question').value=d.text}catch(e){out.textContent=e.message}}
async function askUploadedImage(){let file=document.getElementById('imageFile').files[0];if(!file){alert('Choose an image first.');return}let form=new FormData();form.append('file',file);let q=document.getElementById('visionQuestion').value.trim()||'Describe the main objects and read visible text if possible.';let out=document.getElementById('visionAnswer');out.textContent='Analyzing with local vision model...';try{let d=await api('/api/vision?question='+encodeURIComponent(q),{method:'POST',headers:{'X-Dashboard-Pin':dashboardPin},body:form});out.textContent=d.answer+'\n\nOCR text: '+(d.ocr_text||'(no text detected)')+'\nModel: '+d.model+' · offline'}catch(e){out.textContent=e.message}}
async function toggleCameraControl(){try{let d=await api('/api/camera/control',{method:'POST',body:JSON.stringify({enabled:!cameraEnabled})});cameraEnabled=d.dashboard_camera_enabled;await loadStatus()}catch(e){alert(e.message)}}
async function askGlasses(){let question=document.getElementById('visionQuestion').value.trim();if(!question){alert('Enter a visual question first.');return}let out=document.getElementById('visionAnswer');out.textContent='Waiting for the paired glasses. The physical privacy switch must be on...';try{let d=await api('/api/device/capture',{method:'POST',body:JSON.stringify({question})});out.textContent=d.answer+'\n\nOCR text: '+(d.ocr_text||'(no text detected)')+'\nModel: '+d.model+' · offline'}catch(e){out.textContent=e.message}}
loadStatus();loadMemories();loadWakePhrase();setInterval(loadStatus,5000);
</script></body></html>
"""
