"""앱 생존 확인.

비개발자가 만든 앱은 어느 날 조용히 꺼집니다. 그래서 서버가 주기적으로
"살아있니?" 하고 물어보고, 안 되면 앱스토어에 표시하고 등록자에게 알립니다.
등록자 연락처를 받아 둔 이유가 여기 있습니다.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from app.config import get_settings
from app.db import SessionLocal
from app.mcp_client import client as mcp
from app.models import App, AppStatus, Notification, RuntimeLocation

logger = logging.getLogger(__name__)
settings = get_settings()


async def check_one(db, app: App) -> bool:
    """앱 하나에 접속해 봅니다. 성공하면 True."""
    if not app.endpoint:
        return False
    try:
        await mcp.list_tools(
            app.endpoint, headers=app.auth_headers or {}, timeout=15.0
        )
    except Exception as exc:
        app.consecutive_failures += 1
        app.last_error = f"{type(exc).__name__}: {exc}"[:500]
        app.status = AppStatus.unreachable

        # 연속으로 계속 실패하면 등록자에게 한 번 알립니다(매번 알리지는 않습니다).
        if (
            app.consecutive_failures == settings.healthcheck_failure_threshold
            and app.owner_user_id
        ):
            db.add(
                Notification(
                    user_id=app.owner_user_id,
                    kind="app_down",
                    title=f"'{app.name}' 앱이 응답하지 않습니다",
                    body=(
                        f"{app.consecutive_failures}회 연속으로 접속에 실패했습니다.\n"
                        f"주소: {app.endpoint}\n마지막 오류: {app.last_error}"
                    ),
                    target_id=app.id,
                )
            )
        return False

    app.consecutive_failures = 0
    app.last_error = ""
    app.last_seen_at = datetime.now(timezone.utc)
    if app.status == AppStatus.unreachable:
        app.status = AppStatus.active
    return True


async def sweep() -> dict:
    """등록된 앱을 한 바퀴 돌며 확인합니다."""
    db = SessionLocal()
    try:
        apps = (
            db.query(App)
            .filter(
                App.status != AppStatus.disabled,
                # PC 구동형은 Launcher 를 통해 확인하므로 여기서는 건너뜁니다.
                App.runtime_location == RuntimeLocation.server,
            )
            .all()
        )
        results = await asyncio.gather(*(check_one(db, app) for app in apps))
        db.commit()
        alive = sum(1 for ok in results if ok)
        return {"checked": len(apps), "alive": alive, "down": len(apps) - alive}
    finally:
        db.close()


async def run_forever() -> None:
    """서버가 떠 있는 동안 주기적으로 확인합니다."""
    interval = settings.healthcheck_interval_seconds
    if interval <= 0:
        logger.info("[healthcheck] 꺼져 있습니다 (HEALTHCHECK_INTERVAL_SECONDS=0)")
        return

    while True:
        await asyncio.sleep(interval)
        try:
            summary = await sweep()
            logger.info("[healthcheck] %s", summary)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("[healthcheck] 실패: %s", exc)
