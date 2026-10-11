from __future__ import annotations

import sqlite3
from pathlib import Path


def search_memories(db_path: Path, query: str, limit: int = 5) -> list[str]:
    """Simple local keyword overlap retrieval; no external embeddings required."""
    words = {word.casefold().strip(".,!?;:'\"()[]{}") for word in query.split()}
    words = {word for word in words if len(word) > 2}
    if not words:
        return []
    with sqlite3.connect(db_path) as db:
        rows = db.execute("SELECT content FROM memories ORDER BY id DESC LIMIT 100").fetchall()
    ranked: list[tuple[int, str]] = []
    for (content,) in rows:
        normalized = content.casefold()
        score = sum(1 for word in words if word in normalized)
        if score:
            ranked.append((score, content))
    ranked.sort(key=lambda item: item[0], reverse=True)
    return [content for _, content in ranked[:limit]]
