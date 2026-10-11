from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "memory.sqlite3"
DATA_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="AI Glasses Local Dashboard", version="0.1.0")


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


init_db()


class MemoryInput(BaseModel):
    content: Annotated[str, Field(min_length=1, max_length=1000)]


@app.get("/", response_class=HTMLResponse)
def dashboard() -> str:
    return DASHBOARD_HTML


@app.get("/api/status")
def status() -> dict:
    return {
        "app": "running",
        "mode": "local scaffold",
        "language_model": "not configured",
        "speech_recognition": "not configured",
        "text_to_speech": "not configured",
        "vision_ocr": "not configured",
        "glasses_device": "not connected",
        "camera": "unavailable",
        "microphone": "unavailable",
        "memory": "local SQLite enabled",
        "network_dashboard": "disabled; localhost only",
    }


@app.get("/api/memory")
def list_memories() -> dict:
    with connect_db() as db:
        rows = db.execute(
            "SELECT id, content, created_at FROM memories ORDER BY id DESC"
        ).fetchall()
    return {"items": [dict(row) for row in rows]}


@app.post("/api/memory", status_code=201)
def add_memory(payload: MemoryInput) -> dict:
    content = payload.content.strip()
    if not content:
        raise HTTPException(status_code=422, detail="Memory cannot be blank.")
    timestamp = datetime.now(timezone.utc).isoformat()
    with connect_db() as db:
        cursor = db.execute(
            "INSERT INTO memories (content, created_at) VALUES (?, ?)",
            (content, timestamp),
        )
        memory_id = cursor.lastrowid
    return {"id": memory_id, "content": content, "created_at": timestamp}


@app.delete("/api/memory/{memory_id}")
def delete_memory(memory_id: int) -> dict:
    with connect_db() as db:
        cursor = db.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Memory not found.")
    return {"deleted": memory_id}


@app.delete("/api/memory")
def clear_memories() -> dict:
    with connect_db() as db:
        db.execute("DELETE FROM memories")
    return {"cleared": True}


@app.post("/api/ask")
def ask(payload: MemoryInput) -> dict:
    return {
        "status": "not_configured",
        "message": (
            "The local AI model is not connected yet. This scaffold does not send "
            "your question to a cloud service."
        ),
        "question_received": payload.content.strip(),
    }


DASHBOARD_HTML = r"""
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AI Glasses | Local Control</title>
<style>
:root{color-scheme:dark;--bg:#080d15;--panel:rgba(18,29,45,.9);--line:#263a51;--cyan:#65dcff;--muted:#9db0c5;--text:#eaf5ff;--warn:#ffcf70}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(ellipse at 15% 0%,#12304a 0,transparent 45%),var(--bg);color:var(--text);font:15px/1.5 system-ui,Segoe UI,sans-serif}
main{max-width:1100px;margin:auto;padding:28px 18px 60px}.eyebrow{color:var(--cyan);letter-spacing:.16em;text-transform:uppercase;font-size:.75rem;font-weight:700}
h1{font-size:clamp(2rem,5vw,3.5rem);line-height:1.05;margin:.5rem 0}h2{font-size:1.1rem;margin:0 0 14px}.sub{color:var(--muted);max-width:700px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:14px;margin:24px 0}
.card{background:var(--panel);border:1px solid var(--line);border-radius:18px;padding:18px;box-shadow:0 12px 35px #0003}
.status{display:inline-flex;align-items:center;gap:8px;color:var(--warn);font-size:.86rem}.dot{width:8px;height:8px;border-radius:50%;background:var(--warn);display:inline-block}
.kv{display:flex;justify-content:space-between;gap:12px;padding:8px 0;border-bottom:1px solid #263a5166}.kv:last-child{border:0}.kv span:first-child{color:var(--muted)}.kv span:last-child{text-align:right;overflow-wrap:anywhere}
label{display:block;color:var(--muted);margin:12px 0 5px}textarea,button{font:inherit;border-radius:10px;border:1px solid var(--line);padding:11px 12px}textarea{width:100%;background:#080f19;color:var(--text);min-height:82px;resize:vertical}
button{background:#153c51;color:var(--text);cursor:pointer;margin:3px 3px 3px 0}button:hover{border-color:var(--cyan)}button.secondary{background:#101a27}button.danger{background:#3a2028;border-color:#633540}
.item{border:1px solid var(--line);border-radius:10px;padding:10px;margin:8px 0;overflow-wrap:anywhere}.item small{color:var(--muted)}.note{border-left:3px solid var(--cyan);padding:10px 12px;background:#0c1c2a;color:#bfd8e9;border-radius:0 8px 8px 0}.footer{color:var(--muted);font-size:.82rem;margin-top:24px}
</style></head>
<body><main>
<div class="eyebrow">LOCAL-FIRST PROTOTYPE · BUILD 0.1</div>
<h1>AI <span style="color:var(--cyan)">Glasses</span></h1>
<p class="sub">Laptop-hosted assistant foundation. This dashboard reports the real scaffold status and will not pretend unconnected hardware or models are working.</p>
<div class="grid">
<section class="card"><div class="status"><i class="dot"></i><span>Scaffold running</span></div><h2 style="margin-top:12px">System status</h2><div id="status">Loading status...</div></section>
<section class="card"><h2>Ask the local assistant</h2><p class="sub">Question handling is a placeholder until an offline model is installed.</p><label for="question">Question</label><textarea id="question" placeholder="Ask a test question..."></textarea><button onclick="ask()">Submit question</button><p id="answer" role="status"></p></section>
<section class="card"><h2>Local memory</h2><p class="sub">Test persistent memory storage. Entries are saved on this laptop in SQLite.</p><label for="memory">Useful fact or summary</label><textarea id="memory" placeholder="Example: My exhibition is on October 22."></textarea><button onclick="saveMemory()">Save memory</button><button class="secondary" onclick="loadMemories()">Refresh</button><button class="danger" onclick="clearMemory()">Clear all</button><div id="memories" aria-live="polite"></div></section>
<section class="card"><h2>Hardware privacy</h2><div class="note">No camera or microphone is connected in this software scaffold. Capture is unavailable, not silently enabled.</div><div class="kv"><span>Camera</span><span>Not connected</span></div><div class="kv"><span>Physical privacy switch</span><span>Not implemented</span></div><div class="kv"><span>Capture indicator</span><span>Not implemented</span></div></section>
</div><p class="footer">Privacy: this build binds to localhost only. Do not expose it to Wi-Fi until authentication and access controls are added. No cloud AI is called by this scaffold.</p>
</main>
<script>
async function api(url,options){options=options||{};options.headers=Object.assign({'Content-Type':'application/json'},options.headers||{});var r=await fetch(url,options);var data=await r.json();if(!r.ok)throw new Error(data.detail||'Request failed');return data}
function esc(s){return String(s).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]})}
async function loadStatus(){try{var s=await api('/api/status');document.getElementById('status').innerHTML=Object.entries(s).map(function(p){return '<div class="kv"><span>'+esc(p[0].replace(/_/g,' '))+'</span><span>'+esc(p[1])+'</span></div>'}).join('')}catch(e){document.getElementById('status').textContent=e.message}}
async function loadMemories(){try{var d=await api('/api/memory');var el=document.getElementById('memories');el.innerHTML=d.items.length?d.items.map(function(m){return '<div class="item">'+esc(m.content)+'<br><small>'+esc(new Date(m.created_at).toLocaleString())+'</small> <button class="secondary" onclick="deleteMemory('+m.id+')">Delete</button></div>'}).join(''):'<p class="sub">No saved memories yet.</p>'}catch(e){document.getElementById('memories').textContent=e.message}}
async function saveMemory(){var content=document.getElementById('memory').value.trim();if(!content)return;try{await api('/api/memory',{method:'POST',body:JSON.stringify({content:content})});document.getElementById('memory').value='';await loadMemories()}catch(e){alert(e.message)}}
async function deleteMemory(id){try{await api('/api/memory/'+id,{method:'DELETE'});await loadMemories()}catch(e){alert(e.message)}}
async function clearMemory(){if(!confirm('Delete every saved memory from this local database?'))return;try{await api('/api/memory',{method:'DELETE'});await loadMemories()}catch(e){alert(e.message)}}
async function ask(){var content=document.getElementById('question').value.trim();if(!content)return;try{var d=await api('/api/ask',{method:'POST',body:JSON.stringify({content:content})});document.getElementById('answer').textContent=d.message}catch(e){document.getElementById('answer').textContent=e.message}}
loadStatus();loadMemories();setInterval(loadStatus,10000);
</script></body></html>
"""
