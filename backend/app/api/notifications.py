"""알림 - 내 앱이 죽었을 때 등록자에게 알려 주는 용도."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import current_user
from app.models import Notification

router = APIRouter(prefix="/api/notifications", tags=["알림"])


@router.get("", summary="내 알림")
def list_notifications(
    unread_only: bool = False,
    limit: int = 50,
    db: Session = Depends(get_db),
    user_id: str = Depends(current_user),
) -> list[dict]:
    query = db.query(Notification).filter(Notification.user_id == user_id)
    if unread_only:
        query = query.filter(Notification.read.is_(False))
    rows = query.order_by(Notification.created_at.desc()).limit(min(limit, 200)).all()
    return [
        {
            "id": row.id,
            "kind": row.kind,
            "title": row.title,
            "body": row.body,
            "target_id": row.target_id,
            "read": row.read,
            "at": row.created_at.isoformat() if row.created_at else "",
        }
        for row in rows
    ]


@router.post("/{notification_id}/read", status_code=204, response_model=None,
             summary="읽음 표시")
def mark_read(
    notification_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(current_user),
) -> None:
    row = db.get(Notification, notification_id)
    if row is None or row.user_id != user_id:
        raise HTTPException(404, "알림을 찾을 수 없습니다.")
    row.read = True
    db.commit()
