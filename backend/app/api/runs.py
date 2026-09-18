"""실행 API - 자연어 요청을 넣고 결과를 받아 봅니다."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import current_user
from app.models import AgentCard, Run
from app.schemas import RunCreateIn, RunOut
from app.worker.queue import get_queue
from app.worker.tasks import process_run

router = APIRouter(prefix="/api/runs", tags=["실행"])


@router.post("", response_model=RunOut, status_code=202, summary="자연어 요청 실행")
def create_run(
    payload: RunCreateIn,
    db: Session = Depends(get_db),
    user_id: str = Depends(current_user),
) -> Run:
    app_ids = list(payload.app_ids)

    # 카드로 실행하면 그 카드에 담긴 앱만 후보로 씁니다.
    if payload.card_id and not app_ids:
        card = db.get(AgentCard, payload.card_id)
        if card is None or card.user_id != user_id:
            raise HTTPException(404, "카드를 찾을 수 없습니다.")
        app_ids = list(card.app_ids or [])

    run = Run(
        user_id=user_id,
        card_id=payload.card_id,
        request_text=payload.request_text,
        app_ids=app_ids,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    # 오래 걸릴 수 있으므로 큐에 넣고 바로 응답합니다.
    get_queue().enqueue(process_run, run.id)
    return run


@router.get("", response_model=list[RunOut], summary="내 실행 이력")
def list_runs(
    limit: int = 20,
    db: Session = Depends(get_db),
    user_id: str = Depends(current_user),
) -> list[Run]:
    return (
        db.query(Run)
        .filter(Run.user_id == user_id)
        .order_by(Run.created_at.desc())
        .limit(min(limit, 100))
        .all()
    )


@router.get("/{run_id}", response_model=RunOut, summary="실행 상태/결과 조회")
def get_run(
    run_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(current_user),
) -> Run:
    run = db.get(Run, run_id)
    if run is None or run.user_id != user_id:
        raise HTTPException(404, "실행 기록을 찾을 수 없습니다.")
    db.refresh(run)
    return run
