"""예약 API - "시간이 되면 알아서 해라".

회신기한 리마인드, 수명업무 기한 알림, 매주 월요일 주간보고 초안 만들기가
전부 여기로 들어옵니다.

되돌릴 수 없는 앱(메일 발송 등)이 들어간 예약은 저장할 때 한 번 확인을 받습니다.
예약이 실제로 도는 순간에는 사람이 화면 앞에 없어서 그때는 물어볼 수 없기 때문입니다.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.audit import record
from app.db import get_db
from app.deps import current_user
from app.models import (
    App,
    AppStatus,
    AppVisibility,
    Recipe,
    Schedule,
    ScheduleAction,
    ScheduleTrigger,
)
from app.scheduler import service as scheduler
from app.schemas import ScheduleIn, ScheduleOut
from app.worker.queue import get_queue
from app.worker.tasks import run_schedule

router = APIRouter(prefix="/api/schedules", tags=["예약"])


def _owned(db: Session, schedule_id: str, user_id: str) -> Schedule:
    row = db.get(Schedule, schedule_id)
    if row is None or row.user_id != user_id:
        raise HTTPException(404, "예약을 찾을 수 없습니다.")
    return row


def _out(row: Schedule) -> ScheduleOut:
    data = ScheduleOut.model_validate(row)
    data.when_text = scheduler.describe(row)
    return data


def _usable_apps(db: Session, app_ids: list[str], user_id: str) -> list[App]:
    """이 사용자가 실제로 부를 수 있는 앱만 골라 돌려줍니다."""
    if not app_ids:
        return []
    return (
        db.query(App)
        .filter(
            App.id.in_(app_ids),
            App.status == AppStatus.active,
            (App.visibility == AppVisibility.approved) | (App.owner_user_id == user_id),
        )
        .all()
    )


def _validate(db: Session, payload: ScheduleIn, user_id: str) -> None:
    """저장하기 전에 말이 되는 예약인지 봅니다."""
    if payload.trigger == ScheduleTrigger.once and payload.run_at is None:
        raise HTTPException(400, "한 번만 도는 예약은 기준 시각(run_at)이 필요합니다.")
    if payload.trigger == ScheduleTrigger.daily and not payload.at_time:
        raise HTTPException(400, "매일 도는 예약은 시각(at_time, 예: 09:00)이 필요합니다.")
    if payload.trigger == ScheduleTrigger.interval and payload.interval_minutes <= 0:
        raise HTTPException(400, "반복 예약은 간격(interval_minutes)이 필요합니다.")

    if payload.action == ScheduleAction.request and not payload.request_text.strip():
        raise HTTPException(400, "무엇을 요청할지 적어 주세요.")

    # 확인이 필요한 앱이 끼어 있는지 미리 봅니다.
    risky: list[str] = []
    if payload.action == ScheduleAction.recipe:
        target = db.get(Recipe, payload.recipe_id) if payload.recipe_id else None
        if target is None or target.user_id != user_id:
            raise HTTPException(404, "레시피를 찾을 수 없습니다.")
        step_ids = [s.get("app_id", "") for s in target.steps or []]
        risky = [a.name for a in _usable_apps(db, step_ids, user_id) if a.requires_confirmation]
    elif payload.action == ScheduleAction.tool:
        apps = _usable_apps(db, [payload.app_id], user_id)
        if not apps:
            raise HTTPException(404, "앱을 찾을 수 없거나 쓸 수 없는 앱입니다.")
        if not payload.tool_name:
            raise HTTPException(400, "부를 기능 이름(tool_name)을 적어 주세요.")
        risky = [a.name for a in apps if a.requires_confirmation]
    else:
        # 자연어 요청은 어떤 앱을 쓸지 실행해 봐야 알 수 있어, 후보에 위험한 앱이
        # 있으면 미리 확인을 받습니다. 후보를 비워 두면 전체 앱이 후보입니다.
        candidates = _usable_apps(db, payload.app_ids, user_id) if payload.app_ids else (
            db.query(App)
            .filter(
                App.status == AppStatus.active,
                (App.visibility == AppVisibility.approved)
                | (App.owner_user_id == user_id),
            )
            .all()
        )
        risky = [a.name for a in candidates if a.requires_confirmation]

    if risky and not payload.pre_approved:
        raise HTTPException(
            400,
            "되돌릴 수 없는 작업이 들어 있습니다: "
            + ", ".join(sorted(set(risky))[:5])
            + ". 예약이 도는 순간에는 확인을 받을 수 없으니, "
            "'자동 실행을 허용합니다'에 체크해 주세요.",
        )


@router.get("", response_model=list[ScheduleOut], summary="내 예약 목록")
def list_schedules(
    include_done: bool = False,
    db: Session = Depends(get_db),
    user_id: str = Depends(current_user),
) -> list[ScheduleOut]:
    query = db.query(Schedule).filter(Schedule.user_id == user_id)
    if not include_done:
        query = query.filter(Schedule.enabled.is_(True))
    rows = query.order_by(Schedule.next_run_at.asc().nullslast(), Schedule.created_at).all()
    return [_out(row) for row in rows]


@router.post("", response_model=ScheduleOut, status_code=201, summary="예약 만들기")
def create_schedule(
    payload: ScheduleIn,
    request: Request,
    db: Session = Depends(get_db),
    user_id: str = Depends(current_user),
) -> ScheduleOut:
    _validate(db, payload, user_id)

    row = Schedule(user_id=user_id, **payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)

    scheduler.arm(db, row)  # 여기서 실제로 큐에 시간이 걸립니다
    db.refresh(row)
    record(db, user_id, "schedule_created", "schedule", row.id,
           {"title": row.title, "when": scheduler.describe(row)}, request)
    return _out(row)


@router.get("/{schedule_id}", response_model=ScheduleOut, summary="예약 상세")
def get_schedule(
    schedule_id: str, db: Session = Depends(get_db), user_id: str = Depends(current_user)
) -> ScheduleOut:
    return _out(_owned(db, schedule_id, user_id))


@router.put("/{schedule_id}", response_model=ScheduleOut, summary="예약 수정")
def update_schedule(
    schedule_id: str,
    payload: ScheduleIn,
    db: Session = Depends(get_db),
    user_id: str = Depends(current_user),
) -> ScheduleOut:
    row = _owned(db, schedule_id, user_id)
    _validate(db, payload, user_id)

    for key, value in payload.model_dump().items():
        setattr(row, key, value)
    db.commit()

    scheduler.arm(db, row)  # 시각이 바뀌었을 수 있으니 다시 걸어 줍니다
    db.refresh(row)
    return _out(row)


@router.post("/{schedule_id}/cancel", response_model=ScheduleOut, summary="예약 끄기")
def cancel_schedule(
    schedule_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user_id: str = Depends(current_user),
) -> ScheduleOut:
    """예약을 끕니다. 기록은 남으므로 나중에 다시 켤 수 있습니다."""
    row = _owned(db, schedule_id, user_id)
    row.enabled = False
    db.commit()
    scheduler.disarm(row)
    row.next_run_at = None
    db.commit()
    db.refresh(row)
    record(db, user_id, "schedule_cancelled", "schedule", row.id, {"title": row.title}, request)
    return _out(row)


@router.post("/{schedule_id}/resume", response_model=ScheduleOut, summary="예약 다시 켜기")
def resume_schedule(
    schedule_id: str, db: Session = Depends(get_db), user_id: str = Depends(current_user)
) -> ScheduleOut:
    row = _owned(db, schedule_id, user_id)
    if scheduler.compute_next_run(row) is None:
        raise HTTPException(409, "이 예약은 이미 지나갔습니다. 시각을 새로 정해 주세요.")

    row.enabled = True
    db.commit()
    scheduler.arm(db, row)
    db.refresh(row)
    return _out(row)


@router.post("/{schedule_id}/run-now", response_model=ScheduleOut, status_code=202,
             summary="지금 바로 한 번 돌려보기")
def run_now(
    schedule_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user_id: str = Depends(current_user),
) -> ScheduleOut:
    """예약이 제대로 도는지 기다리지 않고 확인해 보는 용도입니다.

    실행 기록은 worker 가 만들기 때문에 여기서는 예약 정보를 그대로 돌려줍니다.
    잠시 뒤 이 예약의 last_run_id 에 방금 실행한 기록이 붙습니다.
    """
    row = _owned(db, schedule_id, user_id)
    get_queue().enqueue(run_schedule, row.id)
    record(db, user_id, "schedule_run_now", "schedule", row.id, {"title": row.title}, request)
    return _out(row)


@router.delete("/{schedule_id}", status_code=204, response_model=None,
               summary="예약 삭제")
def delete_schedule(
    schedule_id: str, db: Session = Depends(get_db), user_id: str = Depends(current_user)
) -> None:
    row = _owned(db, schedule_id, user_id)
    scheduler.disarm(row)
    db.delete(row)
    db.commit()
