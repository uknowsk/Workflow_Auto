"""보낸 메일과 회신 현황 저장소.

"누구에게 언제 무엇을 보냈고, 회신 기한이 언제이며, 답이 왔는가"를 남깁니다.
이 표가 있어야 미회신자 목록과 리마인드가 가능합니다.
"""
import os
import sqlite3
import uuid
from datetime import datetime, timezone

import dates

DB_PATH = os.getenv("MAIL_DB", "/srv/data/mail.db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS mails (
  id            TEXT PRIMARY KEY,
  thread_key    TEXT NOT NULL DEFAULT '',  -- 같은 건으로 묶는 키. 예) meeting:<회의록id>
  to_addr       TEXT NOT NULL,
  to_name       TEXT NOT NULL DEFAULT '',
  subject       TEXT NOT NULL DEFAULT '',
  body          TEXT NOT NULL DEFAULT '',
  kind          TEXT NOT NULL DEFAULT 'normal',  -- normal | reminder
  reply_due     TEXT NOT NULL DEFAULT '',        -- 회신 기한 YYYY-MM-DD
  sent_at       TEXT NOT NULL,
  adapter       TEXT NOT NULL DEFAULT '',        -- mock=가짜 메일함, smtp=사내 메일
  provider_id   TEXT NOT NULL DEFAULT '',        -- 메일 서버가 준 식별자
  replied_at    TEXT NOT NULL DEFAULT '',
  reply_body    TEXT NOT NULL DEFAULT '',
  reminder_count    INTEGER NOT NULL DEFAULT 0,
  last_reminder_at  TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_mails_thread ON mails(thread_key);
CREATE INDEX IF NOT EXISTS idx_mails_replied ON mails(replied_at);
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


def _shape(row: sqlite3.Row, with_body: bool = False) -> dict:
    item = dict(row)
    item["replied"] = bool(item["replied_at"])
    left = dates.days_left(item["reply_due"])
    item["days_left"] = left
    # 기한이 지났는데 아직 답이 없는 건 = 리마인드 대상
    item["overdue"] = bool(not item["replied"] and left is not None and left < 0)
    if not with_body:
        item.pop("body", None)
    return item


def record_sent(
    to_addr: str,
    to_name: str,
    subject: str,
    body: str,
    thread_key: str = "",
    reply_due: str = "",
    kind: str = "normal",
    adapter: str = "",
    provider_id: str = "",
) -> dict:
    mail_id = str(uuid.uuid4())
    with connect() as conn:
        conn.execute(
            "INSERT INTO mails (id, thread_key, to_addr, to_name, subject, body, kind,"
            " reply_due, sent_at, adapter, provider_id) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                mail_id,
                thread_key.strip(),
                to_addr.strip(),
                to_name.strip(),
                subject,
                body,
                kind,
                dates.parse_due(reply_due),
                _now(),
                adapter,
                provider_id,
            ),
        )
    return get(mail_id, with_body=True) or {}


def get(mail_id: str, with_body: bool = False) -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM mails WHERE id = ?", (mail_id,)).fetchone()
    return _shape(row, with_body=with_body) if row else None


def search(thread_key: str = "", limit: int = 50, kind: str = "all") -> list[dict]:
    where: list[str] = []
    params: list[str] = []
    if thread_key:
        where.append("thread_key = ?")
        params.append(thread_key.strip())
    if kind in ("normal", "reminder"):
        where.append("kind = ?")
        params.append(kind)

    sql = "SELECT * FROM mails"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY sent_at DESC LIMIT ?"
    params.append(str(max(1, min(limit, 200))))

    with connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_shape(row) for row in rows]


def unreplied(thread_key: str = "", overdue_only: bool = False) -> list[dict]:
    """아직 답이 없는 메일. overdue_only 면 회신 기한이 지난 것만."""
    items = [m for m in search(thread_key=thread_key, limit=200) if not m["replied"]]
    if overdue_only:
        items = [m for m in items if m["overdue"]]
    # 한 사람에게 원본 + 리마인드가 여러 통 갔을 수 있으니 사람 기준으로 한 번만 남깁니다.
    seen: dict = {}
    for item in sorted(items, key=lambda m: (m["kind"] != "normal", m["sent_at"])):
        seen.setdefault((item["thread_key"], item["to_addr"]), item)
    return list(seen.values())


def mark_replied(mail_id: str, body: str = "") -> dict | None:
    with connect() as conn:
        conn.execute(
            "UPDATE mails SET replied_at = ?, reply_body = ? WHERE id = ?",
            (_now(), body, mail_id),
        )
        # 같은 사람에게 같은 건으로 보낸 리마인드도 함께 회신 처리합니다.
        row = conn.execute(
            "SELECT thread_key, to_addr FROM mails WHERE id = ?", (mail_id,)
        ).fetchone()
        if row and row["thread_key"]:
            conn.execute(
                "UPDATE mails SET replied_at = ? WHERE thread_key = ? AND to_addr = ?"
                " AND replied_at = ''",
                (_now(), row["thread_key"], row["to_addr"]),
            )
    return get(mail_id, with_body=True)


def bump_reminder(mail_id: str) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE mails SET reminder_count = reminder_count + 1, last_reminder_at = ?"
            " WHERE id = ?",
            (_now(), mail_id),
        )


def thread_summary(thread_key: str = "") -> dict:
    items = search(thread_key=thread_key, limit=200)
    replied = [m for m in items if m["replied"]]
    pending = [m for m in items if not m["replied"]]
    return {
        "sent_count": len(items),
        "replied_count": len(replied),
        "unreplied_count": len(pending),
        "overdue_count": len([m for m in pending if m["overdue"]]),
    }
