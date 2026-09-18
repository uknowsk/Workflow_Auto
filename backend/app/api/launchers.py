"""Launcher API - 개인 PC에서 앱을 실행하는 연결 프로그램.

왜 필요한가
  Workflow Auto 는 서버에서 돕니다. 개인 PC에 설치된 앱은 그 PC 안에 있어서
  서버가 직접 실행할 방법이 없습니다. 그래서 PC 쪽에 Launcher 를 깔고,
  Launcher 가 서버에 "일 있나요?" 하고 물어보러 오게 합니다.
  PC 에서 밖으로 나가는 연결만 쓰므로 방화벽을 열 필요가 없습니다.

  ┌────────┐   ① 일 있나요?   ┌────────┐
  │Launcher│ ───────────────> │ 서버   │
  │ (내 PC)│ <─────────────── │        │
  └────────┘   ② 이거 해줘     └────────┘
       │ ③ PC의 앱 실행
       └──────> ④ 결과 보내기 ──> 서버

지금 단계
  등록과 작업 주고받기 자리까지만 만들어 두었습니다.
  실제 Launcher 프로그램(설치 파일)은 다음 단계입니다.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.audit import record
from app.auth.passwords import hash_password, verify_password
from app.db import get_db
from app.deps import current_user
from app.models import Launcher, LauncherJob

router = APIRouter(prefix="/api/launchers", tags=["Launcher"])


class LauncherRegisterIn(BaseModel):
    hostname: str = ""


class LauncherRegisterOut(BaseModel):
    launcher_id: str
    token: str
    note: str = "이 토큰은 지금 한 번만 보여집니다. Launcher 설정에 넣어 두세요."


class JobOut(BaseModel):
    job_id: str
    app_id: str
    tool_name: str
    arguments: dict


class JobResultIn(BaseModel):
    output: str = ""
    error: str = ""


@router.post("", response_model=LauncherRegisterOut, status_code=201,
             summary="내 PC의 Launcher 등록")
def register_launcher(
    payload: LauncherRegisterIn,
    request: Request,
    db: Session = Depends(get_db),
    user_id: str = Depends(current_user),
) -> LauncherRegisterOut:
    token = secrets.token_urlsafe(32)
    launcher = Launcher(
        user_id=user_id, hostname=payload.hostname, token_hash=hash_password(token)
    )
    db.add(launcher)
    db.commit()
    db.refresh(launcher)
    record(db, user_id, "launcher_registered", "launcher", launcher.id,
           {"hostname": payload.hostname}, request)
    return LauncherRegisterOut(launcher_id=launcher.id, token=token)


def _authenticate(db: Session, launcher_id: str, token: str) -> Launcher:
    launcher = db.get(Launcher, launcher_id)
    if launcher is None or not verify_password(token, launcher.token_hash):
        raise HTTPException(401, "Launcher 인증에 실패했습니다.")
    launcher.last_seen_at = datetime.now(timezone.utc)
    db.commit()
    return launcher


@router.get("/{launcher_id}/jobs", response_model=list[JobOut],
            summary="할 일 가져가기 (Launcher 가 호출)")
def poll_jobs(
    launcher_id: str,
    x_launcher_token: str = Header(default=""),
    limit: int = 5,
    db: Session = Depends(get_db),
) -> list[JobOut]:
    _authenticate(db, launcher_id, x_launcher_token)

    jobs = (
        db.query(LauncherJob)
        .filter(LauncherJob.launcher_id == launcher_id, LauncherJob.status == "pending")
        .order_by(LauncherJob.created_at)
        .limit(min(limit, 20))
        .all()
    )
    for job in jobs:
        job.status = "taken"
    db.commit()

    return [
        JobOut(
            job_id=job.id,
            app_id=job.app_id,
            tool_name=job.tool_name,
            arguments=job.arguments or {},
        )
        for job in jobs
    ]


@router.post("/{launcher_id}/jobs/{job_id}/result", status_code=204, response_model=None,
             summary="실행 결과 보내기 (Launcher 가 호출)")
def submit_result(
    launcher_id: str,
    job_id: str,
    payload: JobResultIn,
    x_launcher_token: str = Header(default=""),
    db: Session = Depends(get_db),
) -> None:
    _authenticate(db, launcher_id, x_launcher_token)

    job = db.get(LauncherJob, job_id)
    if job is None or job.launcher_id != launcher_id:
        raise HTTPException(404, "작업을 찾을 수 없습니다.")

    job.output = payload.output
    job.error = payload.error
    job.status = "failed" if payload.error else "done"
    job.finished_at = datetime.now(timezone.utc)
    db.commit()


@router.get("", summary="내 Launcher 목록")
def list_launchers(
    db: Session = Depends(get_db), user_id: str = Depends(current_user)
) -> list[dict]:
    return [
        {
            "launcher_id": launcher.id,
            "hostname": launcher.hostname,
            "last_seen_at": launcher.last_seen_at.isoformat()
            if launcher.last_seen_at
            else None,
        }
        for launcher in db.query(Launcher).filter(Launcher.user_id == user_id).all()
    ]
