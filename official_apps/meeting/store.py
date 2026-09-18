"""정리한 회의록 보관소. SQLite 파일 하나입니다."""
import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone

DB_PATH = os.getenv("MEETING_DB", "/srv/data/meeting.db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS meetings (
  id         TEXT PRIMARY KEY,
  title      TEXT NOT NULL DEFAULT '',
  date       TEXT NOT NULL DEFAULT '',
  attendees  TEXT NOT NULL DEFAULT '[]',
  notes      TEXT NOT NULL DEFAULT '',   -- 원본 메모. 나중에 다시 볼 수 있게 남깁니다
  summary    TEXT NOT NULL DEFAULT '',
  decisions  TEXT NOT NULL DEFAULT '[]',
  todos      TEXT NOT NULL DEFAULT '[]',
  source     TEXT NOT NULL DEFAULT '',   -- llm=LLM이 정리, rule=규칙으로 정리
  created_at TEXT NOT NULL
);
"""


def connect() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init() -> None:
    with connect() as conn:
        conn.executescript(_SCHEMA)


def _shape(row: sqlite3.Row, with_notes: bool = True) -> dict:
    item = dict(row)
    for key in ("attendees", "decisions", "todos"):
        item[key] = json.loads(item.get(key) or "[]")
    if not with_notes:
        item.pop("notes", None)
    return item


def save(
    title: str,
    date: str,
    attendees: list,
    notes: str,
    summary: str,
    decisions: list,
    todos: list,
    source: str,
) -> dict:
    meeting_id = str(uuid.uuid4())
    with connect() as conn:
        conn.execute(
            "INSERT INTO meetings (id, title, date, attendees, notes, summary,"
            " decisions, todos, source, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                meeting_id,
                title,
                date,
                json.dumps(attendees, ensure_ascii=False),
                notes,
                summary,
                json.dumps(decisions, ensure_ascii=False),
                json.dumps(todos, ensure_ascii=False),
                source,
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
            ),
        )
    return get(meeting_id) or {}


def get(meeting_id: str) -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM meetings WHERE id = ?", (meeting_id,)).fetchone()
    return _shape(row) if row else None


def recent(limit: int = 20) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM meetings ORDER BY created_at DESC LIMIT ?",
            (max(1, min(limit, 100)),),
        ).fetchall()
    # 목록에서는 원본 메모를 빼서 결과를 가볍게 유지합니다.
    return [_shape(row, with_notes=False) for row in rows]
