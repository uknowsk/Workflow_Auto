"""Gauss 사용 한도.

한 사람이 실수로 몰아 쓰면 그 달 내내 다 같이 멈출 수 있습니다. 그래서
1인당 월 한도를 둡니다. 한도는 관리자가 화면에서 정하고,
**기본값은 0 = 제한 없음**입니다(아직 회사 한도 숫자를 모르기 때문).

숫자를 알게 되면 화면에서 넣기만 하면 켜집니다.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app import notify, settings_store
from app.models import LlmUsage


def current_period() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def used_this_month(db: Session, user_id: str, period: str | None = None) -> int:
    """이 사람이 이번 달에 쓴 토큰 수."""
    if not user_id:
        return 0
    total = (
        db.query(func.coalesce(func.sum(LlmUsage.total_tokens), 0))
        .filter(LlmUsage.user_id == user_id, LlmUsage.period == (period or current_period()))
        .scalar()
    )
    return int(total or 0)


def limit(db: Session) -> int:
    """0 이면 제한 없음."""
    return settings_store.get(db, "llm_monthly_token_limit")


def check(db: Session, user_id: str) -> str:
    """한도를 넘었으면 사용자에게 보여 줄 말을, 괜찮으면 빈 글자를 돌려줍니다.

    실행을 시작하기 전에 부릅니다. 이미 돌고 있는 작업을 중간에 끊지는 않습니다
    (반쯤 한 일이 더 곤란합니다).
    """
    allowed = limit(db)
    if allowed <= 0:
        return ""

    used = used_this_month(db, user_id)
    if used < allowed:
        return ""

    return (
        f"이번 달 Gauss 사용 한도를 다 썼습니다 ({used:,} / {allowed:,} 토큰).\n"
        "다음 달이 되면 다시 쓸 수 있습니다. 급하면 관리자에게 한도를 늘려 달라고 하세요."
    )


def notify_admins_once(db: Session, user_id: str) -> None:
    """한도에 걸린 사람이 있다고 관리자에게 알립니다.

    같은 사람 같은 달에 한 번만 보냅니다. 요청할 때마다 알리면 관리자 알림함이
    그 사람 이름으로 가득 찹니다.
    """
    from app.models import Notification  # 순환 import 를 피해 여기서 읽습니다

    period = current_period()
    target = f"quota:{user_id}:{period}"
    already = (
        db.query(Notification)
        .filter(Notification.kind == "quota_exceeded", Notification.target_id == target)
        .first()
    )
    if already is not None:
        return

    notify.send_many(
        db,
        notify.admin_ids(db),
        kind="quota_exceeded",
        title=f"{user_id} 님이 이번 달 Gauss 한도를 다 썼습니다",
        body=(
            f"{period} 사용량 {used_this_month(db, user_id):,} 토큰, "
            f"한도 {limit(db):,} 토큰.\n"
            "관리자 화면 > Gauss 사용량 에서 한도를 바꿀 수 있습니다."
        ),
        target_id=target,
    )
