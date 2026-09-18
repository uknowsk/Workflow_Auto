"""감사 기록 조회 - 관리자 전용."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_admin
from app.models import AuditLog

router = APIRouter(prefix="/api/audit", tags=["감사"])


@router.get("", summary="감사 기록 조회(관리자)")
def list_audit(
    db: Session = Depends(get_db),
    _: str = Depends(require_admin),
    actor: str | None = Query(default=None, description="사번으로 거르기"),
    action: str | None = Query(default=None, description="행동으로 거르기"),
    target_id: str | None = Query(default=None),
    since: str | None = Query(default=None, description="이 시각 이후. ISO 형식"),
    limit: int = Query(default=100, le=500),
) -> list[dict]:
    query = db.query(AuditLog)
    if actor:
        query = query.filter(AuditLog.actor == actor)
    if action:
        query = query.filter(AuditLog.action == action)
    if target_id:
        query = query.filter(AuditLog.target_id == target_id)
    if since:
        query = query.filter(AuditLog.created_at >= since)

    rows = query.order_by(AuditLog.created_at.desc()).limit(limit).all()
    return [
        {
            "at": row.created_at.isoformat() if row.created_at else "",
            "actor": row.actor,
            "action": row.action,
            "target": f"{row.target_type}:{row.target_id}" if row.target_type else "",
            "detail": row.detail,
            "ip": row.client_ip,
        }
        for row in rows
    ]


@router.get("/actions", summary="기록되는 행동 목록")
def list_actions(db: Session = Depends(get_db), _: str = Depends(require_admin)) -> list[str]:
    return sorted({row[0] for row in db.query(AuditLog.action).distinct().all()})
