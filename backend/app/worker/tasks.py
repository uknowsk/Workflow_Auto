"""백그라운드 작업 본체. rq worker 가 이 함수를 실행합니다."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from app.db import SessionLocal
from app.models import Run, RunStatus
from app.orchestrator.engine import run_request


def process_run(run_id: str) -> None:
    db = SessionLocal()
    try:
        run = db.get(Run, run_id)
        if run is None:
            return

        run.status = RunStatus.running
        run.started_at = datetime.now(timezone.utc)
        db.commit()

        def save_steps(steps: list[dict]) -> None:
            """앱을 하나 호출할 때마다 진행상황을 저장 -> 화면에서 바로 보입니다."""
            run.steps = steps
            db.commit()

        try:
            result = asyncio.run(
                run_request(
                    db,
                    run.request_text,
                    app_ids=list(run.app_ids or []),
                    user_id=run.user_id,
                    run_id=run.id,
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
