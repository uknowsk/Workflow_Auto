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
from app.deps import current_user, is_admin, require_admin
from app.models import App, AppCallLog, LlmUsage

router = APIRouter(prefix="/api/stats", tags=["통계"])


def current_period() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


@router.get("/apps", summary="앱 활용도 순위(이달의 앱) - 관리자 전용")
def app_ranking_api(
    admin: str = Depends(require_admin),
    db: Session = Depends(get_db),
    period: str | None = Query(
        default=None, description="집계할 달. YYYY-MM. 비우면 이번 달."
    ),
    limit: int = Query(default=20, le=100),
) -> dict:
    return app_ranking(db, period, limit)


def app_ranking(db: Session, period: str | None = None, limit: int = 20) -> dict:
    """순위 계산 알맹이. 권한 검사는 부르는 쪽에서 합니다."""
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


@router.get("/apps/{app_id}/failures", summary="앱 실패 내역(유지보수용) - 관리자 전용")
def recent_failures(
    app_id: str,
    admin: str = Depends(require_admin),
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


@router.get("/usage", summary="Gauss 사용량 확인")
def llm_usage(
    db: Session = Depends(get_db),
    user_id: str = Depends(current_user),
    period: str | None = Query(default=None, description="집계할 달. YYYY-MM. 비우면 이번 달."),
) -> dict:
    """토큰을 얼마나 썼는지 봅니다.

    일반 사용자는 자기 사용량만, 관리자는 전체와 사용자별 순위를 봅니다.
    (지금은 확인만 하고 한도로 막지는 않습니다.)
    """
    target = period or current_period()
    admin = is_admin(user_id)

    def totals(query):
        row = query.with_entities(
            func.coalesce(func.sum(LlmUsage.prompt_tokens), 0),
            func.coalesce(func.sum(LlmUsage.completion_tokens), 0),
            func.coalesce(func.sum(LlmUsage.total_tokens), 0),
            func.count(LlmUsage.id),
        ).one()
        return {
            "prompt_tokens": int(row[0]),
            "completion_tokens": int(row[1]),
            "total_tokens": int(row[2]),
            "calls": int(row[3]),
        }

    base = db.query(LlmUsage).filter(LlmUsage.period == target)
    result = {
        "period": target,
        "mine": totals(base.filter(LlmUsage.user_id == user_id)),
    }

    if admin:
        result["all_users"] = totals(base)
        rows = (
            db.query(
                LlmUsage.user_id,
                func.sum(LlmUsage.total_tokens).label("tokens"),
                func.count(LlmUsage.id).label("calls"),
            )
            .filter(LlmUsage.period == target)
            .group_by(LlmUsage.user_id)
            .order_by(func.sum(LlmUsage.total_tokens).desc())
            .limit(50)
            .all()
        )
        result["by_user"] = [
            {"user_id": r.user_id, "total_tokens": int(r.tokens or 0), "calls": int(r.calls)}
            for r in rows
        ]
        daily = (
            db.query(LlmUsage.day, func.sum(LlmUsage.total_tokens).label("tokens"))
            .filter(LlmUsage.period == target)
            .group_by(LlmUsage.day)
            .order_by(LlmUsage.day)
            .all()
        )
        result["by_day"] = [
            {"day": d.day, "total_tokens": int(d.tokens or 0)} for d in daily
        ]

    return result
