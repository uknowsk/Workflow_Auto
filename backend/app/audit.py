"""감사 기록.

"누가, 언제, 어떤 요청으로, 어떤 앱이 무엇을 했는지"를 남깁니다.
사내 보안 요건에서 거의 확실히 요구되는 부분입니다.

원칙
  - 사람이 한 행동과 앱 호출을 남깁니다.
  - 요청문이나 결과 "원문 전체"는 남기지 않고 앞부분 요약만 남깁니다.
    (감사에는 충분하고, 개인정보를 통째로 복사해 두지 않기 위해서입니다)
  - 기록에 실패해도 사용자의 작업은 계속돼야 하므로 예외를 삼킵니다.
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models import AuditLog

logger = logging.getLogger(__name__)

SUMMARY_LIMIT = 300


def summarize(value: Any, limit: int = SUMMARY_LIMIT) -> str:
    text = value if isinstance(value, str) else repr(value)
    return text[:limit] + ("…" if len(text) > limit else "")


def record(
    db: Session,
    actor: str,
    action: str,
    target_type: str = "",
    target_id: str = "",
    detail: dict | None = None,
    request: Any = None,
) -> None:
    client_ip = ""
    if request is not None and getattr(request, "client", None):
        client_ip = request.client.host or ""

    try:
        db.add(
            AuditLog(
                actor=actor,
                action=action,
                target_type=target_type,
                target_id=str(target_id)[:64],
                detail=detail or {},
                client_ip=client_ip,
            )
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.warning("감사 기록 실패 (%s/%s): %s", action, target_id, exc)
