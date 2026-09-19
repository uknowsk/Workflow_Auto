"""개인 대시보드 - 로그인하고 처음 보는 화면.

여기 뜨는 것은 두 종류입니다.

  1) 플랫폼이 스스로 아는 것   : 예약된 작업, 최근 실행 결과, 이달의 앱 순위
  2) 앱에게 물어봐야 아는 것   : 오늘 마감 할 일, 회신 안 온 메일, 수명업무 ...

2번은 플랫폼이 직접 계산하지 않습니다. 그 데이터는 할 일 앱, 메일 앱이 들고
있으니까요. 대신 "역할 태그가 todo 인 앱에게 list_due_tasks 를 물어봐라" 같은
규칙만 들고 있다가, 그런 앱이 등록돼 있으면 불러서 채우고 없으면 빈 칸으로 둡니다.
그래서 앱이 나중에 생겨도 대시보드 코드를 고칠 일이 없습니다.

어떤 칸을 띄울지는 DASHBOARD_WIDGETS_FILE 로 바꿔 끼울 수 있습니다.
(예시: config/dashboard.widgets.example.json)
"""
from __future__ import annotations

import asyncio
import json
import logging
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.stats import app_ranking
from app.config import get_settings
from app.db import get_db
from app.deps import current_user, is_admin, is_admin_token
from app.mcp_client import client as mcp
from app.models import App, AppStatus, AppVisibility, Recipe, Run, Schedule, User
from app.orchestrator import recipe as recipe_engine
from app.scheduler import service as scheduler

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/api/dashboard", tags=["개인 대시보드"])

# 기본으로 띄우는 칸들. 사내 앱 이름이 다르면 설정 파일로 덮어쓰면 됩니다.
DEFAULT_WIDGETS: list[dict] = [
    {
        "key": "today_tasks",
        "title": "곧 마감인 할 일 (3일 내)",
        "icon": "✅",
        "capability_tag": "할일관리",
        "tool": "list_due_soon",
        "arguments": {"days": 3, "owner": "{{user_name}}"},
        "hint": "할 일 앱(역할 태그 할일관리)을 앱스토어에 등록하면 여기에 채워집니다.",
    },
    {
        "key": "awaiting_replies",
        "title": "회신 안 온 메일",
        "icon": "📮",
        "capability_tag": "사내메일",
        "tool": "list_unreplied",
        "arguments": {"overdue_only": False},
        "hint": "사내 메일 앱(역할 태그 사내메일)을 등록하면 여기에 채워집니다.",
    },
    {
        "key": "assignments",
        "title": "수명업무",
        "icon": "📌",
        "capability_tag": "할일관리",
        "tool": "list_tasks",
        "arguments": {"kind": "order", "status": "open", "owner": "{{user_name}}"},
        "hint": "할 일 앱(역할 태그 할일관리)을 등록하면 여기에 채워집니다.",
    },
    {
        "key": "deliverables",
        "title": "내 프로젝트 · 다음 산출물",
        "icon": "📁",
        "capability_tag": "개발프로젝트관리",
        "tool": "list_my_projects",
        "arguments": {"user_id": "{{user_id}}"},
        "hint": "개발 프로젝트 앱(역할 태그 개발프로젝트관리)을 등록하면 여기에 채워집니다.",
    },
]


# ── 앱이 돌려준 답을 사람이 읽을 수 있는 몇 줄로 ──────────────────────
# 앱은 MCP 규약대로 JSON 을 돌려줍니다. 그대로 화면에 뿌리면 첫 화면이
# 중괄호로 뒤덮이므로, 여기서 "제목 · 곁들이는 말" 형태의 줄로 바꿉니다.
# 앱 이름을 박아 두지 않고 흔히 쓰는 칸 이름만 봅니다. 모르는 모양이면
# 원래 답을 그대로 둡니다(앱이 새로 생겨도 이 코드를 고칠 일이 없게).

_TITLE_KEYS = ("title", "subject", "name", "label", "summary", "text")
_WHO_KEYS = ("owner", "to_name", "assignee", "orderer", "approver", "participant")
_STATE_KEYS = ("stage", "current_step", "role", "status_text")
_DATE_KEYS = ("due", "due_date", "reply_due", "deadline", "date", "when")
_LIST_SKIP = {"count", "overdue_count", "unreplied_count", "sent_count", "replied_count"}
_MAX_LINES = 6


def _line(item: object) -> str:
    """항목 하나를 한 줄로."""
    if not isinstance(item, dict):
        return str(item)
    head = next((str(item[k]) for k in _TITLE_KEYS if item.get(k)), "")
    if not head:
        return ", ".join(f"{k} {v}" for k, v in list(item.items())[:3])
    tail: list[str] = []
    for keys in (_WHO_KEYS, _STATE_KEYS):
        value = next((str(item[k]) for k in keys if item.get(k)), "")
        if value:
            tail.append(value)
    date = next((str(item[k]) for k in _DATE_KEYS if item.get(k)), "")
    if date:
        tail.append(f"{date}까지")
    days = item.get("days_left")
    if isinstance(days, int) and not isinstance(days, bool):
        tail.append("오늘 마감" if days == 0 else (f"{-days}일 지남" if days < 0 else f"{days}일 남음"))
    return f"{head} · {' · '.join(tail)}" if tail else head


def summarize(text: str) -> str:
    """앱의 JSON 답을 짧은 목록으로. 못 알아보면 받은 그대로 돌려줍니다."""
    try:
        payload = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return text
    if isinstance(payload, dict):
        rows = next(
            (v for k, v in payload.items() if k not in _LIST_SKIP and isinstance(v, list)),
            None,
        )
    elif isinstance(payload, list):
        rows = payload
    else:
        return text
    if rows is None:
        return text
    if not rows:
        return ""
    lines = [_line(row) for row in rows[:_MAX_LINES]]
    if len(rows) > _MAX_LINES:
        lines.append(f"… 외 {len(rows) - _MAX_LINES}건")
    return "\n".join(lines)


@lru_cache
def load_widgets() -> list[dict]:
    path = settings.dashboard_widgets_file
    if not path:
        return DEFAULT_WIDGETS
    file = Path(path)
    if not file.is_file():
        logger.warning("[dashboard] 설정 파일이 없어 기본값을 씁니다: %s", file)
        return DEFAULT_WIDGETS
    try:
        payload = json.loads(file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        logger.warning("[dashboard] 설정 파일을 읽지 못해 기본값을 씁니다: %s", exc)
        return DEFAULT_WIDGETS
    return payload.get("widgets", []) if isinstance(payload, dict) else payload


def _pick_app(db: Session, capability_tag: str, user_id: str) -> App | None:
    """그 역할을 맡은 앱 하나를 고릅니다. 내가 올린 개인 앱이 공식 앱보다 우선입니다."""
    candidates = (
        db.query(App)
        .filter(
            App.capability_tag == capability_tag,
            App.status == AppStatus.active,
            (App.visibility == AppVisibility.approved) | (App.owner_user_id == user_id),
        )
        .all()
    )
    if not candidates:
        return None
    mine = [a for a in candidates if a.owner_user_id == user_id]
    return (mine or candidates)[0]


async def _fetch_widget(
    db: Session, widget: dict, user_id: str, user_name: str = ""
) -> dict:
    """칸 하나를 채웁니다. 앱이 없거나 느려도 빈 칸으로 돌려주고 넘어갑니다."""
    result = {
        "key": widget.get("key", ""),
        "title": widget.get("title", ""),
        "icon": widget.get("icon", "📋"),
        "status": "missing",
        "app": "",
        "text": "",
        "hint": widget.get("hint", ""),
    }

    app = _pick_app(db, widget.get("capability_tag", ""), user_id)
    if app is None:
        return result

    tool_name = widget.get("tool", "")
    if tool_name not in {t.name for t in app.tools}:
        result["app"] = app.name
        result["hint"] = f"'{app.name}' 앱에 '{tool_name}' 기능이 없습니다."
        return result

    arguments = recipe_engine.fill(
        widget.get("arguments") or {},
        recipe_engine.base_context(user_id, user_name),
    )
    result["app"] = app.name
    try:
        text, is_error = await mcp.call_tool(
            app.endpoint,
            tool_name,
            arguments,
            headers=app.auth_headers or {},
            timeout=settings.dashboard_timeout,
        )
    except Exception as exc:
        result["status"] = "error"
        result["text"] = f"앱을 부르지 못했습니다: {exc}"
        return result

    if is_error:
        result["status"] = "error"
        result["text"] = text[:2000]
        return result
    readable = summarize(text)
    result["status"] = "ok" if readable.strip() else "empty"
    result["text"] = readable[:2000]
    return result


@router.get("", summary="첫 화면에 모아 보여줄 것들")
async def dashboard(
    db: Session = Depends(get_db),
    user_id: str = Depends(current_user),
    token_admin: bool = Depends(is_admin_token),
) -> dict:
    # 앱에게 물어보는 칸들은 한꺼번에 물어봅니다(하나씩 기다리면 화면이 늦게 뜹니다).
    # 할 일 앱처럼 담당자를 이름으로 들고 있는 앱이 있어 표시 이름도 함께 넘깁니다.
    me = db.query(User).filter(User.user_id == user_id).first()
    user_name = me.name if me and me.name else user_id

    widgets = await asyncio.gather(
        *(
            _fetch_widget(db, widget, user_id, user_name)
            for widget in load_widgets()
        )
    )

    upcoming = (
        db.query(Schedule)
        .filter(Schedule.user_id == user_id, Schedule.enabled.is_(True))
        .order_by(Schedule.next_run_at.asc().nullslast())
        .limit(5)
        .all()
    )
    recent = (
        db.query(Run)
        .filter(Run.user_id == user_id)
        .order_by(Run.created_at.desc())
        .limit(5)
        .all()
    )
    recipes = (
        db.query(Recipe)
        .filter(Recipe.user_id == user_id)
        .order_by(Recipe.last_run_at.desc().nullslast(), Recipe.created_at.desc())
        .limit(5)
        .all()
    )

    return {
        "user_id": user_id,
        "widgets": list(widgets),
        "schedules": [
            {
                "id": row.id,
                "title": row.title,
                "when_text": scheduler.describe(row),
                "next_run_at": row.next_run_at.isoformat() if row.next_run_at else "",
                "last_status": row.last_status,
            }
            for row in upcoming
        ],
        "runs": [
            {
                "id": row.id,
                "request_text": row.request_text[:120],
                "status": row.status.value,
                "created_at": row.created_at.isoformat() if row.created_at else "",
            }
            for row in recent
        ],
        "recipes": [
            {
                "id": row.id,
                "title": row.title,
                "icon": row.icon,
                "run_count": row.run_count or 0,
            }
            for row in recipes
        ],
        # "이달의 앱"은 앱 순위라서 관리자에게만 보냅니다.
        "ranking": (
            app_ranking(db=db, period=None, limit=3)["ranking"]
            if (token_admin or is_admin(user_id))
            else []
        ),
    }
