"""오래된 기록 지우기.

실행 이력에는 요청문과 결과물이 통째로 남습니다. 회의록이나 메일 본문을 넣고
돌렸다면 그 내용 그대로입니다. 그래서 정해진 기간이 지나면 지웁니다.
기간은 관리자가 화면에서 바꿉니다(app/settings_store.py).

0 으로 두면 지우지 않습니다.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app import settings_store
from app.db import SessionLocal
from app.models import AppCallLog, AuditLog, LlmUsage, Run

logger = logging.getLogger(__name__)

# 하루에 한 번이면 충분합니다(기록이 하루 더 남아 있다고 문제가 되지 않습니다).
INTERVAL_SECONDS = 24 * 60 * 60


def _cutoff(days: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days)


def sweep_once(db: Session) -> dict[str, int]:
    """지울 것을 지우고, 무엇을 몇 개 지웠는지 돌려줍니다."""
    removed: dict[str, int] = {}

    run_days = settings_store.get(db, "run_retention_days")
    if run_days > 0:
        cutoff = _cutoff(run_days)
        # 실행 이력에 딸린 기록도 같이 지웁니다. 남겨 두면 "무엇에 대한
        # 기록인지 알 수 없는 줄"만 쌓입니다.
        removed["runs"] = (
            db.query(Run).filter(Run.created_at < cutoff)
            .delete(synchronize_session=False)
        )
        removed["app_call_logs"] = (
            db.query(AppCallLog).filter(AppCallLog.created_at < cutoff)
            .delete(synchronize_session=False)
        )
        removed["llm_usage"] = (
            db.query(LlmUsage).filter(LlmUsage.created_at < cutoff)
            .delete(synchronize_session=False)
        )

    audit_days = settings_store.get(db, "audit_retention_days")
    if audit_days > 0:
        removed["audit_logs"] = (
            db.query(AuditLog).filter(AuditLog.created_at < _cutoff(audit_days))
            .delete(synchronize_session=False)
        )

    db.commit()
    return {name: count for name, count in removed.items() if count}


def sweep() -> dict[str, int]:
    db = SessionLocal()
    try:
        return sweep_once(db)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


async def run_forever() -> None:
    """서버가 떠 있는 동안 하루에 한 번 정리합니다."""
    while True:
        await asyncio.sleep(INTERVAL_SECONDS)
        try:
            summary = sweep()
            if summary:
                logger.info("[cleanup] 오래된 기록을 지웠습니다: %s", summary)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            # 정리가 실패해도 서버는 계속 돌아야 합니다. 내일 다시 시도합니다.
            logger.warning("[cleanup] 실패: %s", exc)
