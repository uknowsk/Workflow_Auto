"""활용도 통계 - '이달의 앱' 순위.

순위는 단순 호출 수가 아니라 "성공한 호출 수" 기준입니다.
많이 불렸어도 계속 실패한 앱이 1등이 되면 안 되니까요.
성공률과 실제로 써 본 사람 수도 같이 돌려줍니다.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, distinct, func
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import App, AppCallLog

router = APIRouter(prefix="/api/stats", tags=["통계"])


def current_period() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


@router.get("/apps", summary="앱 활용도 순위(이달의 앱)")
def app_ranking(
    db: Session = Depends(get_db),
    period: str | None = Query(
        default=None, description="집계할 달. YYYY-MM. 비우면 이번 달."
    ),
    limit: int = Query(default=20, le=100),
) -> dict:
    target = period or current_period()

    success_count = func.sum(case((AppCallLog.success.is_(True), 1), else_=0))
    rows = (
        db.query(
            AppCallLog.app_id,
            AppCallLog.app_name,
            AppCallLog.owner_user_id,
            func.count(AppCallLog.id).label("total_calls"),
            success_count.label("success_calls"),
            func.count(distinct(AppCallLog.user_id)).label("user_count"),
            func.avg(AppCallLog.duration_ms).label("avg_ms"),
        )
        .filter(AppCallLog.period == target)
        .group_by(AppCallLog.app_id, AppCallLog.app_name, AppCallLog.owner_user_id)
        .order_by(success_count.desc(), func.count(distinct(AppCallLog.user_id)).desc())
        .limit(limit)
        .all()
    )

    # 등록자 연락처는 App 에서 가져옵니다(앱이 지워졌으면 로그에 남은 사번만 표시).
    apps = {a.id: a for a in db.query(App).all()}

    ranking = []
    for rank, row in enumerate(rows, start=1):
        app = apps.get(row.app_id)
        total = int(row.total_calls or 0)
        success = int(row.success_calls or 0)
        ranking.append(
            {
                "rank": rank,
                "app_id": row.app_id,
                "name": row.app_name,
                "success_calls": success,
                "total_calls": total,
                "success_rate": round(success / total * 100, 1) if total else 0.0,
                "user_count": int(row.user_count or 0),
                "avg_ms": int(row.avg_ms or 0),
                "owner": {
                    "user_id": row.owner_user_id,
                    "name": app.owner if app else "",
                    "dept": app.owner_dept if app else "",
                    "contact": app.owner_contact if app else "",
                },
            }
        )

    return {"period": target, "ranking": ranking}


@router.get("/apps/{app_id}/failures", summary="앱 실패 내역(유지보수용)")
def recent_failures(
    app_id: str,
    db: Session = Depends(get_db),
    limit: int = Query(default=20, le=100),
) -> list[dict]:
    """앱이 왜 실패했는지 최근 기록. 등록자에게 알려 줄 때 씁니다."""
    rows = (
        db.query(AppCallLog)
        .filter(AppCallLog.app_id == app_id, AppCallLog.success.is_(False))
        .order_by(AppCallLog.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "tool": row.tool_name,
            "error": row.error_summary,
            "at": row.created_at.isoformat() if row.created_at else "",
        }
        for row in rows
    ]
