"""백그라운드 작업 본체. rq worker 가 이 함수를 실행합니다.

처리 순서
  1) 계획 세우기 - 어떤 앱을 어떤 순서로 쓸지
  2) 되돌릴 수 없는 앱이 끼어 있으면 여기서 멈추고 사용자 확인을 기다립니다
  3) 확인이 필요 없거나 이미 승인됐으면 실제로 실행
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from app.db import SessionLocal
from app.models import FormTemplate, Run, RunStatus
from app.orchestrator.engine import load_bindings, make_plan, run_request


def _finish(db, run: Run, status: RunStatus) -> None:
    run.status = status
    run.finished_at = datetime.now(timezone.utc)
    db.commit()


def process_run(run_id: str, approved: bool = False) -> None:
    db = SessionLocal()
    try:
        run = db.get(Run, run_id)
        if run is None:
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
                )
            )
            run.steps = result.steps
            run.result_text = result.result_text
            run.status = RunStatus.succeeded
        except Exception as exc:
            run.error = f"{type(exc).__name__}: {exc}"
            run.status = RunStatus.failed

        run.finished_at = datetime.now(timezone.utc)
        db.commit()
    finally:
        db.close()
