"""실행 API - 자연어 요청을 넣고 결과를 받아 봅니다.

되돌릴 수 없는 앱(메일 발송, 결재 상신 등)이 계획에 끼면 바로 실행하지 않고
계획을 보여 준 뒤 사용자 승인을 기다립니다.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.audit import record, summarize
from app.db import get_db
from app.deps import current_user
from app.models import AgentCard, Run, RunStatus
from app.schemas import RunCreateIn, RunOut
from app.worker.queue import get_queue
from app.worker.tasks import process_recipe_run, process_run

router = APIRouter(prefix="/api/runs", tags=["실행"])

# 더 손댈 수 없는 상태들. 멈추기는 이 상태가 아닐 때만 됩니다.
FINISHED = {
    RunStatus.succeeded,
    RunStatus.failed,
    RunStatus.rejected,
    RunStatus.canceled,
}


def _owned(db: Session, run_id: str, user_id: str) -> Run:
    run = db.get(Run, run_id)
    if run is None or run.user_id != user_id:
        raise HTTPException(404, "실행 기록을 찾을 수 없습니다.")
    return run


@router.post("", response_model=RunOut, status_code=202, summary="자연어 요청 실행")
def create_run(
    payload: RunCreateIn,
    request: Request,
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
        form_id=payload.form_id or "",
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    record(db, user_id, "run_created", "run", run.id,
           {"request": summarize(payload.request_text)}, request)

    # 오래 걸릴 수 있으므로 큐에 넣고 바로 응답합니다.
    get_queue().enqueue(process_run, run.id)
    return run


@router.post("/{run_id}/approve", response_model=RunOut, summary="계획 승인하고 실행")
def approve_run(
    run_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user_id: str = Depends(current_user),
) -> Run:
    """사용자가 계획을 확인하고 '이대로 해'라고 하면 그때 실행합니다."""
    run = _owned(db, run_id, user_id)
    if run.status != RunStatus.awaiting_approval:
        raise HTTPException(409, "지금은 승인할 수 있는 상태가 아닙니다.")

    run.approved_by = user_id
    run.status = RunStatus.queued
    db.commit()
    db.refresh(run)

    record(db, user_id, "run_approved", "run", run.id,
           {"plan": summarize(run.plan_summary)}, request)

    # 레시피 실행이면 계획을 새로 세우지 않고 저장된 단계를 그대로 돌립니다.
    task = process_recipe_run if run.recipe_id else process_run
    get_queue().enqueue(task, run.id, True)
    return run


@router.post("/{run_id}/reject", response_model=RunOut, summary="계획 거부")
def reject_run(
    run_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user_id: str = Depends(current_user),
) -> Run:
    run = _owned(db, run_id, user_id)
    if run.status != RunStatus.awaiting_approval:
        raise HTTPException(409, "지금은 거부할 수 있는 상태가 아닙니다.")

    run.status = RunStatus.rejected
    run.finished_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(run)
    record(db, user_id, "run_rejected", "run", run.id, {}, request)
    return run


@router.post("/{run_id}/cancel", response_model=RunOut, summary="실행 멈추기")
def cancel_run(
    run_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user_id: str = Depends(current_user),
) -> Run:
    """돌아가는 작업을 멈춥니다.

    이미 시작한 앱 호출 하나는 끝까지 갑니다(반쯤 한 일을 늘리지 않으려고).
    그다음 앱으로는 넘어가지 않고 거기서 멈춥니다. 큐에서 차례를 기다리는
    중이었다면 시작조차 하지 않습니다.
    """
    run = _owned(db, run_id, user_id)
    if run.status in FINISHED:
        raise HTTPException(409, "이미 끝난 작업입니다.")

    run.status = RunStatus.canceled
    run.finished_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(run)

    record(db, user_id, "run_canceled", "run", run.id, {}, request)
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
    run = _owned(db, run_id, user_id)
    db.refresh(run)
    return run
