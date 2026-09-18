"""앱 목록 자동 등록.

SEED_FILE 로 지정한 JSON 을 읽어 앱스토어에 등록합니다.
회사에서는 사내 앱 목록 파일만 바꿔 끼우면 되고, 코드는 건드릴 필요가 없습니다.
이미 등록된 slug 는 건너뛰므로 서버를 몇 번 재시작해도 안전합니다.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from app.config import get_settings
from app.db import SessionLocal
from app.mcp_client import client as mcp
from app.auth.passwords import hash_password
from app.models import App, AppStatus, AppTool, AppVisibility, User

logger = logging.getLogger(__name__)
settings = get_settings()

_ALLOWED = {
    "slug", "name", "endpoint", "description", "usage_hint",
    "category", "capability_tag", "owner", "owner_dept", "owner_contact",
    "icon", "auth_headers",
}


async def _sync(db, app: App) -> None:
    try:
        tools = await mcp.list_tools(
            app.endpoint, headers=app.auth_headers or {}, timeout=settings.mcp_timeout
        )
    except Exception as exc:
        # 앱이 아직 안 떴을 수도 있습니다. 나중에 화면에서 '새로고침' 하면 됩니다.
        app.status = AppStatus.unreachable
        app.last_error = f"{type(exc).__name__}: {exc}"
        logger.warning("[seed] %s 기능 목록 읽기 실패: %s", app.slug, exc)
        return
    for tool in tools:
        db.add(
            AppTool(
                app_id=app.id,
                name=tool.name,
                description=tool.description,
                input_schema=tool.input_schema,
            )
        )
    app.status = AppStatus.active
    app.last_error = ""


async def seed_from_file(path: str) -> None:
    file = Path(path)
    if not file.is_file():
        logger.warning("[seed] 파일이 없어 건너뜁니다: %s", file)
        return

    payload = json.loads(file.read_text(encoding="utf-8"))
    entries = payload.get("apps", []) if isinstance(payload, dict) else payload

    db = SessionLocal()
    try:
        for entry in entries:
            slug = entry.get("slug")
            if not slug or db.query(App).filter(App.slug == slug).first():
                continue  # 이미 있으면 그대로 둡니다

            app = App(
                owner_user_id=entry.get("owner_user_id", ""),
                # 목록 파일에 올린 앱은 관리자가 넣은 것으로 보고 공식 앱으로 둡니다.
                visibility=AppVisibility.approved,
                **{k: v for k, v in entry.items() if k in _ALLOWED},
            )
            db.add(app)
            db.flush()
            await _sync(db, app)
            logger.info("[seed] 등록: %s (%s)", app.name, app.status.value)
        db.commit()
    finally:
        db.close()


def seed_bootstrap_admin() -> None:
    """서버가 처음 뜰 때 관리자 계정 하나를 만들어 둡니다.

    계정이 하나도 없으면 아무도 로그인할 수 없으니 최초 1명이 필요합니다.
    이미 있으면 아무것도 하지 않습니다.
    """
    user_id = settings.bootstrap_admin_id
    password = settings.bootstrap_admin_password
    if not user_id or not password:
        return

    db = SessionLocal()
    try:
        if db.query(User).filter(User.user_id == user_id).first():
            return
        db.add(
            User(
                user_id=user_id,
                name="관리자",
                is_admin=True,
                password_hash=hash_password(password),
            )
        )
        db.commit()
        logger.info("[seed] 최초 관리자 계정을 만들었습니다: %s", user_id)
    finally:
        db.close()
