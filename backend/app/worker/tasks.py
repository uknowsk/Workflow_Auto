"""백그라운드 작업 본체. rq worker 가 이 함수를 실행합니다.

여기 있는 일꾼 3종
  process_run        : 자연어 요청 1건 (계획 -> 확인 -> 실행)
  process_recipe_run : 저장해 둔 레시피 재실행
  run_schedule       : 예약 시각이 되면 위 둘 중 하나를 대신 눌러 줍니다

process_run 의 처리 순서
  1) 계획 세우기 - 어떤 앱을 어떤 순서로 쓸지
  2) 되돌릴 수 없는 앱이 끼어 있으면 여기서 멈추고 사용자 확인을 기다립니다
  3) 확인이 필요 없거나 이미 승인됐으면 실제로 실행
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from app import quota
from app.db import SessionLocal
from app.models import (
    FormTemplate,
    Recipe,
    Run,
    RunStatus,
    Schedule,
    ScheduleAction,
)
from app.orchestrator import recipe as recipe_engine
from app.orchestrator.engine import load_bindings, make_plan, run_request

logger = logging.getLogger(__name__)


def _finish(db, run: Run, status: RunStatus) -> None:
    run.status = status
    run.finished_at = datetime.now(timezone.utc)
    db.commit()


def _canceled(run_id: str) -> bool:
    """사용자가 '멈춤'을 눌렀나?

    일꾼이 들고 있는 세션은 시작할 때 읽은 값을 그대로 쓰고 있을 수 있어서,
    **새 세션으로 다시 읽습니다.** 그래야 화면에서 방금 누른 것이 보입니다.
    """
    db = SessionLocal()
    try:
        status = db.query(Run.status).filter(Run.id == run_id).scalar()
        return status == RunStatus.canceled
    except Exception:
        # 확인에 실패했다고 하던 일을 멈추지는 않습니다.
        return False
    finally:
        db.close()


def _start_guard(db, run: Run) -> str:
    """시작 전에 막아야 할 이유가 있으면 그 말을, 없으면 빈 글자를 돌려줍니다."""
    if run.status == RunStatus.canceled:
        # 큐에서 기다리는 동안 사용자가 멈춘 경우입니다.
        return "취소됨"
    blocked = quota.check(db, run.user_id)
    if blocked:
        quota.notify_admins_once(db, run.user_id)
        return blocked
    return ""


def process_run(run_id: str, approved: bool = False) -> None:
    db = SessionLocal()
    try:
        run = db.get(Run, run_id)
        if run is None:
            return

        stop_reason = _start_guard(db, run)
        if stop_reason == "취소됨":
            return
        if stop_reason:
            run.error = stop_reason
            _finish(db, run, RunStatus.failed)
            return

        run.started_at = run.started_at or datetime.now(timezone.utc)
        app_ids = list(run.app_ids or [])

        # ── 1단계: 계획 ──────────────────────────────────────────────
        if not approved:
            run.status = RunStatus.planning
            db.commit()
            try:
                bindings = load_bindings(db, app_ids, run.user_id, run.request_text)
                summary, steps, needs_approval = make_plan(
                    db, run.request_text, bindings, run.user_id, run.id
                )
            except Exception as exc:
                run.error = f"계획 세우기 실패 - {type(exc).__name__}: {exc}"
                _finish(db, run, RunStatus.failed)
                return

            run.plan = steps
            run.plan_summary = summary
            run.needs_approval = needs_approval

            # ── 2단계: 확인이 필요하면 여기서 멈춥니다 ──────────────
            if needs_approval:
                run.status = RunStatus.awaiting_approval
                db.commit()
                return

        # ── 3단계: 실행 ──────────────────────────────────────────────
        run.status = RunStatus.running
        db.commit()

        form_text = ""
        if run.form_id:
            form = db.get(FormTemplate, run.form_id)
            form_text = (form.text_body if form else "") or ""

        def save_steps(steps: list[dict]) -> None:
            """앱을 하나 호출할 때마다 진행상황을 저장 -> 화면에서 바로 보입니다."""
            run.steps = steps
            db.commit()

        try:
            result = asyncio.run(
                run_request(
                    db,
                    run.request_text,
                    app_ids=app_ids,
                    user_id=run.user_id,
                    run_id=run.id,
                    form_text=form_text,
                    on_step=save_steps,
                    should_stop=lambda: _canceled(run.id),
                )
            )
            run.steps = result.steps
            if _canceled(run.id):
                # 사용자가 멈춘 것입니다. 실패로 적으면 뭐가 고장난 줄 압니다.
                run.status = RunStatus.canceled
                run.result_text = ""
            else:
                run.result_text = result.result_text
                run.status = RunStatus.succeeded
        except Exception as exc:
            run.error = f"{type(exc).__name__}: {exc}"
            run.status = RunStatus.failed

        run.finished_at = datetime.now(timezone.utc)
        db.commit()
    finally:
        db.close()


def process_recipe_run(run_id: str, approved: bool = False) -> None:
    """저장해 둔 레시피를 그대로 재실행합니다.

    자연어 요청과 달리 '무엇을 할지'는 이미 정해져 있으므로 계획을 새로 세우지
    않습니다. 다만 되돌릴 수 없는 앱(메일 발송 등)이 들어 있으면 자연어 요청과
    똑같이 한 번 확인을 받습니다.
    """
    db = SessionLocal()
    try:
        run = db.get(Run, run_id)
        if run is None:
            return

        stop_reason = _start_guard(db, run)
        if stop_reason == "취소됨":
            return
        if stop_reason:
            run.error = stop_reason
            _finish(db, run, RunStatus.failed)
            return

        target = db.get(Recipe, run.recipe_id) if run.recipe_id else None
        if target is None:
            run.error = "레시피를 찾을 수 없습니다. 삭제됐는지 확인해 주세요."
            _finish(db, run, RunStatus.failed)
            return

        run.started_at = run.started_at or datetime.now(timezone.utc)
        steps = list(target.steps or [])

        # ── 1단계: 확인이 필요한 앱이 있으면 멈춥니다 ────────────────
        if not approved:
            plan, needs_approval = recipe_engine.plan_from_steps(db, steps, run.user_id)
            run.plan = plan
            run.plan_summary = f"레시피 '{target.title}' 을 {len(plan)}단계로 실행합니다."
            run.needs_approval = needs_approval
            if needs_approval:
                run.status = RunStatus.awaiting_approval
                db.commit()
                return

        # ── 2단계: 실행 ──────────────────────────────────────────────
        run.status = RunStatus.running
        db.commit()

        form_id = run.form_id or target.form_id
        form = db.get(FormTemplate, form_id) if form_id else None
        form_text = (form.text_body if form else "") or ""

        def save_steps(steps_so_far: list[dict]) -> None:
            run.steps = steps_so_far
            db.commit()

        try:
            result = asyncio.run(
                recipe_engine.execute(
                    db,
                    steps,
                    final_instruction=target.final_instruction,
                    form_text=form_text,
                    variables=dict(run.variables or {}),
                    user_id=run.user_id,
                    run_id=run.id,
                    on_step=save_steps,
                    should_stop=lambda: _canceled(run.id),
                )
            )
            run.steps = result.steps
            if _canceled(run.id):
                run.status = RunStatus.canceled
                run.result_text = ""
            else:
                run.result_text = result.result_text
                # 중간에 멈췄으면 실패로 봅니다(화면에서 빨갛게 보이도록).
                failed = any(step.get("error") for step in result.steps)
                run.status = RunStatus.failed if failed else RunStatus.succeeded
                if failed:
                    run.error = result.result_text
        except Exception as exc:
            run.error = f"{type(exc).__name__}: {exc}"
            run.status = RunStatus.failed

        target.run_count = (target.run_count or 0) + 1
        target.last_run_at = datetime.now(timezone.utc)
        run.finished_at = datetime.now(timezone.utc)
        db.commit()
    finally:
        db.close()


def _schedule_run_row(db, schedule: Schedule) -> Run:
    """예약이 만들어 내는 실행 기록 1건. 화면에서는 사람이 누른 것과 똑같이 보입니다."""
    if schedule.action == ScheduleAction.recipe:
        target = db.get(Recipe, schedule.recipe_id) if schedule.recipe_id else None
        title = target.title if target else "(없어진 레시피)"
        return Run(
            user_id=schedule.user_id,
            recipe_id=schedule.recipe_id,
            schedule_id=schedule.id,
            request_text=f"[예약] {schedule.title} - 레시피 '{title}'",
            variables=dict(schedule.variables or {}),
            approved_by=schedule.user_id if schedule.pre_approved else "",
        )

    if schedule.action == ScheduleAction.tool:
        return Run(
            user_id=schedule.user_id,
            schedule_id=schedule.id,
            request_text=f"[예약] {schedule.title} - {schedule.tool_name}",
            approved_by=schedule.user_id if schedule.pre_approved else "",
        )

    return Run(
        user_id=schedule.user_id,
        schedule_id=schedule.id,
        request_text=schedule.request_text,
        app_ids=list(schedule.app_ids or []),
        approved_by=schedule.user_id if schedule.pre_approved else "",
    )


def run_schedule(schedule_id: str) -> None:
    """예약 시각이 되면 worker 가 이 함수를 부릅니다.

    사람이 화면 앞에 없으므로 여기서는 확인을 물어볼 수 없습니다. 그래서 되돌릴 수
    없는 앱이 든 예약은 '만들 때' 확인을 받아 두고(pre_approved), 여기서는 그대로
    실행합니다. 확인을 받지 않은 예약은 계획 화면에서 멈춰 사용자를 기다립니다.
    """
    db = SessionLocal()
    try:
        schedule = db.get(Schedule, schedule_id)
        if schedule is None or not schedule.enabled:
            return

        run = _schedule_run_row(db, schedule)
        db.add(run)
        db.commit()
        db.refresh(run)

        schedule.last_run_at = datetime.now(timezone.utc)
        schedule.last_run_id = run.id
        schedule.run_count = (schedule.run_count or 0) + 1
        schedule.last_error = ""
        db.commit()

        try:
            if schedule.action == ScheduleAction.recipe:
                process_recipe_run(run.id, approved=schedule.pre_approved)
            elif schedule.action == ScheduleAction.tool:
                _run_single_tool(schedule_id, run.id)
            else:
                process_run(run.id, approved=schedule.pre_approved)
        except Exception as exc:
            schedule.last_error = f"{type(exc).__name__}: {exc}"
            logger.warning("[scheduler] 예약 실행 실패 (%s): %s", schedule_id, exc)

        db.refresh(run)
        schedule.last_status = run.status.value
        db.commit()
    finally:
        db.close()

    # 반복 예약이면 다음 차례를 걸어 둡니다. 세션을 새로 열어 깔끔하게 끝냅니다.
    db = SessionLocal()
    try:
        from app.scheduler import service as scheduler

        schedule = db.get(Schedule, schedule_id)
        if schedule is not None:
            scheduler.arm(db, schedule)
    finally:
        db.close()


def _run_single_tool(schedule_id: str, run_id: str) -> None:
    """예약이 앱 기능 하나만 콕 집어 부르는 경우. 레시피 1단계짜리와 같습니다."""
    db = SessionLocal()
    try:
        schedule = db.get(Schedule, schedule_id)
        run = db.get(Run, run_id)
        if schedule is None or run is None:
            return

        steps = [
            {
                "app_id": schedule.app_id,
                "app_name": schedule.title,
                "tool": schedule.tool_name,
                "arguments": dict(schedule.arguments or {}),
                "title": schedule.title,
            }
        ]
        run.status = RunStatus.running
        run.started_at = datetime.now(timezone.utc)
        db.commit()

        try:
            result = asyncio.run(
                recipe_engine.execute(
                    db, steps, user_id=run.user_id, run_id=run.id
                )
            )
            run.steps = result.steps
            run.result_text = result.result_text
            failed = any(step.get("error") for step in result.steps)
            run.status = RunStatus.failed if failed else RunStatus.succeeded
            if failed:
                run.error = result.result_text
        except Exception as exc:
            run.error = f"{type(exc).__name__}: {exc}"
            run.status = RunStatus.failed

        run.finished_at = datetime.now(timezone.utc)
        db.commit()
    finally:
        db.close()
