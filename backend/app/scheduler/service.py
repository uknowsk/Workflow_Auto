"""예약(스케줄러).

시계 역할입니다. "정해진 시각이 되면 이 일을 해라"를 Redis 큐에 미리 걸어 둡니다.
새로 무언가를 띄우지 않고, 이미 돌고 있는 worker 의 예약 기능(rq scheduler)을 씁니다.
  - 예약을 걸 때  : queue.enqueue_at(시각, run_schedule, 예약id)
  - 시각이 되면   : worker 가 run_schedule() 을 실행
  - 반복 예약이면 : 실행이 끝나면서 다음 차례를 다시 걸어 둡니다

시간대: "매일 09시"가 어느 나라 9시인지 정해야 해서 SCHEDULER_TZ_OFFSET_MINUTES
(한국 540분)를 씁니다. 저장은 항상 UTC 로 합니다.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Schedule, ScheduleTrigger
from app.worker.queue import get_queue, get_redis

logger = logging.getLogger(__name__)
settings = get_settings()

WEEKDAY_LABELS = ["월", "화", "수", "목", "금", "토", "일"]


def _offset() -> timedelta:
    return timedelta(minutes=settings.scheduler_tz_offset_minutes)


def to_local(moment: datetime) -> datetime:
    """UTC 시각을 사내 표준시로 바꿉니다(계산용이라 tzinfo 는 뗍니다)."""
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return (moment.astimezone(timezone.utc) + _offset()).replace(tzinfo=None)


def to_utc(local: datetime) -> datetime:
    return (local - _offset()).replace(tzinfo=timezone.utc)


def _parse_at_time(at_time: str) -> tuple[int, int]:
    """'09:30' -> (9, 30). 형식이 이상하면 자정으로 봅니다."""
    try:
        hour, minute = at_time.split(":")
        return max(0, min(23, int(hour))), max(0, min(59, int(minute)))
    except (ValueError, AttributeError):
        return 0, 0


def compute_next_run(schedule: Schedule, after: datetime | None = None) -> datetime | None:
    """다음 실행 시각(UTC)을 계산합니다. 더 돌 일이 없으면 None.

    once  : run_at 에서 lead_minutes 만큼 당긴 시각. 한 번 돌았으면 끝입니다.
            이미 지난 시각이면 지금 바로 돌립니다(기한이 코앞인 리마인드 등).
    daily : 지정한 시각(지정한 요일만). lead_minutes 는 쓰지 않습니다.
    interval : 지금부터 interval_minutes 뒤.
    """
    now = after or datetime.now(timezone.utc)

    if schedule.trigger == ScheduleTrigger.once:
        if schedule.run_at is None or (schedule.run_count or 0) > 0:
            return None
        run_at = schedule.run_at
        if run_at.tzinfo is None:
            run_at = run_at.replace(tzinfo=timezone.utc)
        target = run_at - timedelta(minutes=schedule.lead_minutes or 0)
        return max(target, now + timedelta(seconds=10))

    if schedule.trigger == ScheduleTrigger.interval:
        minutes = max(schedule.interval_minutes or 0, settings.scheduler_min_interval_minutes)
        return now + timedelta(minutes=minutes)

    # daily: 사내 표준시로 계산한 뒤 UTC 로 되돌립니다.
    hour, minute = _parse_at_time(schedule.at_time)
    allowed = {int(d) for d in (schedule.weekdays or [])}
    local = to_local(now)
    candidate = local.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if candidate <= local:
        candidate += timedelta(days=1)
    for _ in range(8):  # 요일 조건이 있으면 최대 일주일 뒤까지 찾습니다
        if not allowed or candidate.weekday() in allowed:
            return to_utc(candidate)
        candidate += timedelta(days=1)
    return None


def describe(schedule: Schedule) -> str:
    """사람이 읽는 한 줄 설명. 화면에 그대로 씁니다."""
    if schedule.trigger == ScheduleTrigger.interval:
        minutes = schedule.interval_minutes or settings.scheduler_min_interval_minutes
        if minutes % 60 == 0:
            return f"{minutes // 60}시간마다"
        return f"{minutes}분마다"

    if schedule.trigger == ScheduleTrigger.daily:
        days = schedule.weekdays or []
        when = "매일" if not days else " ".join(WEEKDAY_LABELS[int(d)] for d in sorted(days))
        return f"{when} {schedule.at_time or '00:00'}"

    if schedule.run_at is None:
        return "시각 미지정"
    local = to_local(schedule.run_at).strftime("%Y-%m-%d %H:%M")
    if schedule.lead_minutes:
        lead = schedule.lead_minutes
        unit = f"{lead // 1440}일" if lead % 1440 == 0 else f"{lead // 60}시간" if lead % 60 == 0 else f"{lead}분"
        return f"{local} 기준 {unit} 전에 한 번"
    return f"{local} 에 한 번"


def disarm(schedule: Schedule) -> None:
    """걸어 둔 예약을 큐에서 뺍니다. 이미 없어졌어도 문제 없습니다."""
    if not schedule.job_id:
        return
    try:
        from rq.job import Job

        job = Job.fetch(schedule.job_id, connection=get_redis())
        job.cancel()
        job.delete()
    except Exception as exc:  # 이미 실행됐거나 사라진 예약
        logger.debug("예약 취소 건너뜀 (%s): %s", schedule.job_id, exc)
    schedule.job_id = ""


def arm(db: Session, schedule: Schedule) -> Schedule:
    """다음 실행 시각을 계산해 큐에 걸어 둡니다.

    예약을 만들거나 고칠 때, 그리고 한 번 실행하고 난 뒤에 부릅니다.
    """
    from app.worker.tasks import run_schedule  # 순환 import 방지

    disarm(schedule)

    if not (schedule.enabled and settings.scheduler_enabled):
        schedule.next_run_at = None
        db.commit()
        return schedule

    next_run = compute_next_run(schedule)
    if next_run is None:
        schedule.enabled = False  # 더 돌 일이 없는 1회성 예약
        schedule.next_run_at = None
        db.commit()
        return schedule

    try:
        job = get_queue().enqueue_at(next_run, run_schedule, schedule.id)
        schedule.job_id = job.id
        schedule.next_run_at = next_run
    except Exception as exc:  # Redis 가 잠깐 죽어 있어도 예약 자체는 남깁니다
        schedule.next_run_at = next_run
        schedule.last_error = f"예약을 큐에 걸지 못했습니다: {exc}"
        logger.warning("예약 등록 실패 (%s): %s", schedule.id, exc)

    db.commit()
    return schedule


def rearm_all(db: Session) -> int:
    """서버가 다시 뜰 때 살아 있는 예약을 전부 다시 걸어 둡니다.

    Redis 가 비워졌거나 서버가 내려가 있는 동안 지나간 예약이 있어도
    이 함수가 다음 차례를 새로 계산해 주므로 예약이 조용히 사라지지 않습니다.
    """
    if not settings.scheduler_enabled:
        return 0
    count = 0
    for schedule in db.query(Schedule).filter(Schedule.enabled.is_(True)).all():
        arm(db, schedule)
        count += 1
    logger.info("[scheduler] 예약 %d건을 다시 걸었습니다.", count)
    return count
