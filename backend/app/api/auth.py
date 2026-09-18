"""로그인 API.

지금은 사번 + 비밀번호입니다. 사내 SSO 로 바꿀 때는
app/auth/backend.py 의 SsoBackend 만 채우면 됩니다.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.audit import record
from app.auth.backend import get_backend
from app.auth.passwords import hash_password
from app.auth.tokens import create_token
from app.config import get_settings
from app.db import get_db
from app.deps import current_user, require_admin
from app.models import User

router = APIRouter(prefix="/api/auth", tags=["로그인"])
settings = get_settings()


class LoginIn(BaseModel):
    user_id: str = Field(..., description="사번")
    password: str


class LoginOut(BaseModel):
    token: str
    user_id: str
    name: str
    is_admin: bool


class UserIn(BaseModel):
    user_id: str
    password: str
    name: str = ""
    dept: str = ""
    contact: str = ""
    is_admin: bool = False


class MeOut(BaseModel):
    user_id: str
    name: str
    dept: str
    contact: str
    is_admin: bool


@router.post("/login", response_model=LoginOut, summary="로그인")
def login(payload: LoginIn, request: Request, db: Session = Depends(get_db)) -> LoginOut:
    user = get_backend(settings.auth_backend).authenticate(
        db, payload.user_id, payload.password
    )
    if user is None:
        record(db, payload.user_id, "login_failed", "user", payload.user_id, request=request)
        raise HTTPException(401, "사번 또는 비밀번호가 맞지 않습니다.")

    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    record(db, user.user_id, "login", "user", user.user_id, request=request)

    return LoginOut(
        token=create_token(user.user_id, user.is_admin, settings.token_ttl_seconds),
        user_id=user.user_id,
        name=user.name,
        is_admin=user.is_admin,
    )


@router.get("/me", response_model=MeOut, summary="내 정보")
def me(db: Session = Depends(get_db), user_id: str = Depends(current_user)) -> MeOut:
    user = db.query(User).filter(User.user_id == user_id).first()
    if user is None:
        # 개발 모드(토큰 없이 헤더로만 들어온 경우)
        return MeOut(user_id=user_id, name="", dept="", contact="", is_admin=False)
    return MeOut(
        user_id=user.user_id,
        name=user.name,
        dept=user.dept,
        contact=user.contact,
        is_admin=user.is_admin,
    )


@router.post("/users", response_model=MeOut, status_code=201, summary="계정 만들기(관리자)")
def create_user(
    payload: UserIn,
    request: Request,
    db: Session = Depends(get_db),
    admin: str = Depends(require_admin),
) -> MeOut:
    if db.query(User).filter(User.user_id == payload.user_id).first():
        raise HTTPException(409, f"이미 있는 사번입니다: {payload.user_id}")

    user = User(
        user_id=payload.user_id,
        name=payload.name,
        dept=payload.dept,
        contact=payload.contact,
        is_admin=payload.is_admin,
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    record(db, admin, "user_created", "user", user.user_id, request=request)
    return MeOut(
        user_id=user.user_id,
        name=user.name,
        dept=user.dept,
        contact=user.contact,
        is_admin=user.is_admin,
    )
