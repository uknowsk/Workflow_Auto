"""알림 보내기 - 한 줄 짜리 도우미들.

알림은 Notification 표에 한 줄 남기는 게 전부입니다(화면에서 보여 줍니다).
나중에 회사 메일이나 사내 메신저로도 보내고 싶어지면 여기 send() 안에서
한 줄 더 부르면 되고, 부르는 쪽 코드는 손댈 필요가 없습니다.

알림이 실패해도 하던 일(의견 남기기, 앱 업데이트)은 끝나야 하므로
예외를 삼킵니다. 감사 기록(audit.record)과 같은 생각입니다.
"""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.auth.backend import is_configured_admin
from app.models import AgentCard, Notification, User

logger = logging.getLogger(__name__)


def send(
    db: Session,
    user_id: str,
    kind: str,
    title: str,
    body: str = "",
    target_id: str = "",
) -> None:
    """한 사람에게 알림 한 줄. 받는 사람이 없으면 아무 일도 하지 않습니다."""
    if not user_id:
        return
    try:
        db.add(
            Notification(
                user_id=user_id,
                kind=kind,
                title=title[:256],
                body=body,
                target_id=str(target_id)[:64],
            )
        )
        db.commit()
    except Exception as exc:  # 알림 때문에 본래 작업이 실패하면 안 됩니다
        db.rollback()
        logger.warning("알림 저장 실패 (%s/%s): %s", kind, user_id, exc)


def send_many(
    db: Session,
    user_ids: set[str] | list[str],
    kind: str,
    title: str,
    body: str = "",
    target_id: str = "",
) -> int:
    """여러 사람에게 같은 알림. 보낸 사람 수를 돌려줍니다."""
    sent = 0
    for user_id in {u for u in user_ids if u}:
        send(db, user_id, kind, title, body, target_id)
        sent += 1
    return sent


def admin_ids(db: Session) -> set[str]:
    """관리자 사번 모음.

    계정의 is_admin 플래그와 환경변수(.env) 양쪽을 봅니다. DB 가 비어 있어도
    관리자가 들어올 수 있게 해 둔 구조라서, 한쪽만 보면 알림이 아무에게도
    가지 않는 일이 생깁니다.
    """
    ids = {u.user_id for u in db.query(User).filter(User.is_admin.is_(True)).all()}
    ids |= {u.user_id for u in db.query(User).all() if is_configured_admin(u.user_id)}
    return ids


def card_user_ids(db: Session, app_id: str) -> set[str]:
    """이 앱을 자기 카드에 담아 쓰고 있는 사람들(= 업데이트에 영향받는 사람들)."""
    if not app_id:
        return set()
    return {
        card.user_id
        for card in db.query(AgentCard).all()
        if app_id in (card.app_ids or [])
    }
