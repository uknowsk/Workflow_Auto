"""할 일 저장소.

SQLite 파일 하나에 담습니다. 앱마다 자기 데이터만 갖게 해서, 플랫폼 DB와
얽히지 않도록 했습니다(다른 개발자 앱들도 똑같이 각자 저장합니다).
"""
import os
import sqlite3
import uuid
from datetime import datetime, timezone

import dates

DB_PATH = os.getenv("TASKS_DB", "/srv/data/tasks.db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
  id          TEXT PRIMARY KEY,
  kind        TEXT NOT NULL DEFAULT 'task',   -- task=내 할 일, order=수명업무(지시받은 일)
  title       TEXT NOT NULL,
  owner       TEXT DEFAULT '',                -- 담당자 이름
  owner_email TEXT DEFAULT '',                -- 담당자 메일 (메일 앱이 이어받아 씁니다)
  orderer     TEXT DEFAULT '',                -- 수명업무를 지시한 상급자
  due         TEXT DEFAULT '',                -- 기한 YYYY-MM-DD
  note        TEXT DEFAULT '',
  source      TEXT DEFAULT '',                -- 어디서 나온 일인지. 예) 9/18 주간회의
  source_ref  TEXT DEFAULT '',                -- 회의록 id 등 연결 고리
  status      TEXT NOT NULL DEFAULT 'open',   -- open | done
  created_at  TEXT NOT NULL,
  done_at     TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_owner ON tasks(owner);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init() -> None:
    with connect() as conn:
        conn.executescript(_SCHEMA)


def _shape(row: sqlite3.Row) -> dict:
    """화면과 오케스트레이터가 바로 쓸 수 있게 남은 날짜까지 계산해 돌려줍니다."""
    item = dict(row)
    left = dates.days_left(item.get("due", ""))
    item["days_left"] = left
    item["overdue"] = bool(item["status"] == "open" and left is not None and left < 0)
    return item


def add(
    title: str,
    owner: str = "",
    owner_email: str = "",
    due: str = "",
    note: str = "",
    source: str = "",
    source_ref: str = "",
    kind: str = "task",
    orderer: str = "",
) -> dict:
    task_id = str(uuid.uuid4())
    with connect() as conn:
        conn.execute(
            "INSERT INTO tasks (id, kind, title, owner, owner_email, orderer, due,"
            " note, source, source_ref, status, created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,'open',?)",
            (
                task_id,
                "order" if kind == "order" else "task",
                title.strip(),
                owner.strip(),
                owner_email.strip(),
                orderer.strip(),
                dates.parse_due(due),
                note.strip(),
                source.strip(),
                source_ref.strip(),
                _now(),
            ),
        )
    return get(task_id) or {}


def get(task_id: str) -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    return _shape(row) if row else None


def search(
    owner: str = "",
    status: str = "open",
    kind: str = "all",
    limit: int = 50,
) -> list[dict]:
    where: list[str] = []
    params: list[str] = []
    if owner:
        where.append("owner LIKE ?")
        params.append(f"%{owner.strip()}%")
    if status in ("open", "done"):
        where.append("status = ?")
        params.append(status)
    if kind in ("task", "order"):
        where.append("kind = ?")
        params.append(kind)

    sql = "SELECT * FROM tasks"
    if where:
        sql += " WHERE " + " AND ".join(where)
    # 기한 없는 일(빈 문자열)은 뒤로 보냅니다.
    sql += " ORDER BY CASE WHEN due = '' THEN 1 ELSE 0 END, due, created_at LIMIT ?"
    params.append(str(max(1, min(limit, 200))))

    with connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_shape(row) for row in rows]


def complete(task_id: str) -> dict | None:
    with connect() as conn:
        cursor = conn.execute(
            "UPDATE tasks SET status='done', done_at=? WHERE id=? AND status='open'",
            (_now(), task_id),
        )
        changed = cursor.rowcount
    task = get(task_id)
    if task is not None:
        task["already_done"] = changed == 0
    return task


def due_soon(days: int = 3, owner: str = "") -> list[dict]:
    """기한이 곧 닥친 일 + 이미 지난 일. 둘 다 챙겨야 하니 같이 돌려줍니다."""
    items = [t for t in search(owner=owner, status="open", limit=200) if t["due"]]
    soon = [t for t in items if t["days_left"] is not None and 0 <= t["days_left"] <= days]
    overdue = [t for t in items if t["overdue"]]
    return overdue + soon
