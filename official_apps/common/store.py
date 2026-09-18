"""공식 앱들이 같이 쓰는 아주 작은 저장소.

앱마다 SQLite 파일 하나를 씁니다. 별도 DB 서버가 필요 없고, 폐쇄망에서도
파일 하나만 있으면 돌아갑니다. 파일 위치는 DATA_DIR 환경변수로 바꿉니다.

한 줄(record)은 이렇게 생겼습니다.

    {"id": "...", "kind": "project", "user_id": "E1001",
     "created_at": "...", "updated_at": "...", "name": "...", ...}

kind 는 "이게 무슨 종류의 기록인가"(프로젝트/업적/결재...)이고,
나머지 항목은 앱이 자유롭게 넣습니다. 컬럼을 미리 정하지 않아도 되므로
앱마다 스키마 파일을 따로 만들 필요가 없습니다.
"""
from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DATA_DIR = Path(os.getenv("DATA_DIR", "./data"))


def now_iso() -> str:
    """지금 시각을 '2026-09-18T14:30:00+00:00' 모양으로."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def today_iso() -> str:
    """오늘 날짜를 '2026-09-18' 모양으로."""
    return datetime.now(timezone.utc).date().isoformat()


class Store:
    """기록을 넣고 빼는 가장 단순한 창고."""

    def __init__(self, name: str) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.path = DATA_DIR / f"{name}.sqlite3"
        self._init_table()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_table(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS records (
                    id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    user_id TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    data TEXT NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_kind ON records (kind, user_id)")

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict:
        record = dict(json.loads(row["data"]))
        record.update(
            {
                "id": row["id"],
                "kind": row["kind"],
                "user_id": row["user_id"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
        )
        return record

    def put(self, kind: str, data: dict, user_id: str = "") -> dict:
        """기록 하나를 새로 넣고, 넣은 결과를 그대로 돌려줍니다."""
        record_id = uuid.uuid4().hex[:12]
        stamp = now_iso()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO records (id, kind, user_id, created_at, updated_at, data)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (record_id, kind, user_id, stamp, stamp, json.dumps(data, ensure_ascii=False)),
            )
        return {
            "id": record_id,
            "kind": kind,
            "user_id": user_id,
            "created_at": stamp,
            "updated_at": stamp,
            **data,
        }

    def get(self, record_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM records WHERE id = ?", (record_id,)).fetchone()
        return self._row_to_dict(row) if row else None

    def list(self, kind: str, user_id: str = "", **filters: Any) -> list[dict]:
        """종류(kind)로 기록을 모아 옵니다. user_id 를 주면 그 사람 것만.

        filters 로 넘긴 값들은 기록 안의 항목과 정확히 일치하는 것만 남깁니다.
        값이 빈 문자열이면 조건에서 빼므로, 인자를 안 채운 경우도 안전합니다.
        """
        sql = "SELECT * FROM records WHERE kind = ?"
        params: list[Any] = [kind]
        if user_id:
            sql += " AND user_id = ?"
            params.append(user_id)
        sql += " ORDER BY created_at"
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()

        records = [self._row_to_dict(row) for row in rows]
        for key, value in filters.items():
            if value in ("", None):
                continue
            records = [r for r in records if r.get(key) == value]
        return records

    def update(self, record_id: str, **fields: Any) -> dict | None:
        """기존 기록의 일부 항목만 바꿉니다. 없는 id 면 None."""
        current = self.get(record_id)
        if current is None:
            return None
        data = {
            k: v
            for k, v in current.items()
            if k not in ("id", "kind", "user_id", "created_at", "updated_at")
        }
        data.update({k: v for k, v in fields.items() if v is not None})
        stamp = now_iso()
        with self._connect() as conn:
            conn.execute(
                "UPDATE records SET data = ?, updated_at = ? WHERE id = ?",
                (json.dumps(data, ensure_ascii=False), stamp, record_id),
            )
        return {
            "id": record_id,
            "kind": current["kind"],
            "user_id": current["user_id"],
            "created_at": current["created_at"],
            "updated_at": stamp,
            **data,
        }

    def delete(self, record_id: str) -> bool:
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM records WHERE id = ?", (record_id,))
        return cursor.rowcount > 0
