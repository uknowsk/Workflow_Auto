"""관리자 화면 뒤쪽 - 최근 오류와 운영 설정.

무슨 일이 왜 실패했는지 관리자가 한 화면에서 보게 하는 것이 목적입니다.
실패는 세 군데에서 생깁니다.
  1) 실행 자체가 실패      (Run.error)        - 사용자가 결과를 못 받음
  2) 앱 호출이 실패        (AppCallLog)       - 앱 하나가 말썽
  3) 앱이 아예 응답 없음   (App.last_error)   - 앱이 꺼져 있음
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import cleanup, settings_store
from app.db import get_db
from app.deps import require_admin
from app.models import App, AppCallLog, AppStatus, Run, RunStatus

router = APIRouter(prefix="/api/admin", tags=["관리자"])


def _when(value: datetime | None) -> str:
    return value.isoformat() if value else ""


@router.get("/errors", summary="최근 오류 모아 보기(관리자)")
def recent_errors(
    db: Session = Depends(get_db),
    _: str = Depends(require_admin),
    days: int = Query(default=7, ge=1, le=90, description="며칠 치를 볼지"),
    limit: int = Query(default=50, le=200, description="종류별 최대 몇 건"),
) -> dict:
    """언제 · 누가 · 무엇을 하다 · 어디서 깨졌는지."""
    since = datetime.now(timezone.utc) - timedelta(days=days)

    failed_runs = (
        db.query(Run)
        .filter(Run.status == RunStatus.failed, Run.created_at >= since)
        .order_by(Run.created_at.desc())
        .limit(limit)
        .all()
    )
    failed_calls = (
        db.query(AppCallLog)
        .filter(AppCallLog.success.is_(False), AppCallLog.created_at >= since)
        .order_by(AppCallLog.created_at.desc())
        .limit(limit)
        .all()
    )
    down_apps = (
        db.query(App)
        .filter(App.status == AppStatus.unreachable)
        .order_by(App.updated_at.desc())
        .limit(limit)
        .all()
    )

    return {
        "days": days,
        "runs": [
            {
                "at": _when(run.finished_at or run.created_at),
                "user_id": run.user_id,
                # 요청문은 앞부분만. 화면에서 한 줄로 보이고, 본문 전체를 관리자
                # 화면에 늘어놓지 않기 위해서이기도 합니다.
                "request": (run.request_text or "")[:120],
                "error": (run.error or "")[:500],
                "run_id": run.id,
            }
            for run in failed_runs
        ],
        "app_calls": [
            {
                "at": _when(call.created_at),
                "app": call.app_name,
                "tool": call.tool_name,
                "user_id": call.user_id,
                "error": (call.error_summary or "")[:500],
                "app_id": call.app_id,
            }
            for call in failed_calls
        ],
        "apps_down": [
            {
                "app": app.name,
                "app_id": app.id,
                "endpoint": app.endpoint,
                "owner": app.owner or app.owner_user_id,
                "contact": app.owner_contact,
                "failures": app.consecutive_failures,
                "error": (app.last_error or "")[:500],
                "last_seen": _when(app.last_seen_at),
            }
            for app in down_apps
        ],
    }


@router.get("/settings", summary="운영 설정 보기(관리자)")
def read_settings(
    db: Session = Depends(get_db), _: str = Depends(require_admin)
) -> list[dict]:
    return settings_store.all_values(db)


@router.put("/settings", summary="운영 설정 바꾸기(관리자)")
def write_settings(
    values: dict[str, int] = Body(..., description='예) {"run_retention_days": 90}'),
    db: Session = Depends(get_db),
    _: str = Depends(require_admin),
) -> list[dict]:
    unknown = set(values) - set(settings_store.BY_KEY)
    if unknown:
        raise HTTPException(400, f"모르는 설정입니다: {', '.join(sorted(unknown))}")
    for key, value in values.items():
        settings_store.set_value(db, key, value)
    return settings_store.all_values(db)


@router.post("/cleanup", summary="오래된 기록 지금 정리(관리자)")
def cleanup_now(db: Session = Depends(get_db), _: str = Depends(require_admin)) -> dict:
    """평소에는 하루에 한 번 저절로 돕니다. 보관 기간을 바꾼 직후처럼
    지금 당장 적용하고 싶을 때 씁니다."""
    return {"removed": cleanup.sweep_once(db)}
