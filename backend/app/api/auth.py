"""로그인 API.

지금은 사번 + 비밀번호입니다. 사내 SSO 로 바꿀 때는
app/auth/backend.py 의 SsoBackend 만 채우면 됩니다.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import departments as dept_service
from app.audit import record
from app.auth.backend import get_backend
from app.auth.passwords import hash_password
from app.auth.tokens import create_token
from app.config import get_settings
from app.db import get_db
from app.deps import current_user, require_admin
from app.models import DeptRole, User
from app.schemas import MyDeptOut

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
    dept: str = Field("", description="소속(글자). 화면에 보여 주는 용도")
    dept_code: str = Field(
        "", description="부서 코드. 넣으면 그 부서의 부서원으로 바로 묶어 줍니다"
    )
    dept_role: DeptRole = Field(
        DeptRole.member, description="member=쓰기만, manager=부서 공통 앱·카드 등록 가능"
    )
    contact: str = ""
    is_admin: bool = False


class MeOut(BaseModel):
    user_id: str
    name: str
    dept: str
    contact: str
    is_admin: bool
    # 개인 설정. 지금은 화면 테마 하나뿐이고, 앞으로 여기에 늘려 갑니다.
    theme: str = "white"
    # 내가 묶여 있는 부서들. 화면은 이걸 보고 부서 공통 카드/앱 버튼을 켭니다.
    depts: list[MyDeptOut] = []


class SettingsIn(BaseModel):
    """내 설정 바꾸기. 넣지 않은 값은 그대로 둡니다."""

    theme: str | None = Field(None, description="화면 테마 이름")


# 고를 수 있는 테마. frontend/lib/theme.ts 의 THEMES 와 같아야 합니다.
THEMES = {"white"}


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
    # 계정의 소속 글자가 부서 표와 똑같으면 부서에 자동으로 묶어 줍니다.
    # (사내 SSO 가 부서를 내려주기 전까지 쓰는 다리입니다)
    dept_service.sync_from_profile(db, user)
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
        # 개발 모드(토큰 없이 헤더로만 들어온 경우). 계정은 없어도 부서에는
        # 묶여 있을 수 있으므로 부서는 채워 줍니다.
        return _me(db, User(user_id=user_id))
    return _me(db, user)


@router.put("/me/settings", response_model=MeOut, summary="내 설정 바꾸기")
def update_settings(
    payload: SettingsIn,
    db: Session = Depends(get_db),
    user_id: str = Depends(current_user),
) -> MeOut:
    user = db.query(User).filter(User.user_id == user_id).first()
    if user is None:
        # 개발 모드에는 저장할 계정이 없으므로 브라우저에 저장된 값만 씁니다.
        return MeOut(
            user_id=user_id,
            name="",
            dept="",
            contact="",
            is_admin=False,
            theme=payload.theme or "white",
        )
    if payload.theme is not None:
        if payload.theme not in THEMES:
            raise HTTPException(400, f"모르는 테마입니다: {payload.theme}")
        user.theme = payload.theme
    db.commit()
    db.refresh(user)
    return _me(db, user)


def _me(db: Session, user: User) -> MeOut:
    rows = dept_service.my_memberships(db, user.user_id)
    names = dept_service.dept_names(db, [row.dept_code for row in rows])
    return MeOut(
        user_id=user.user_id,
        name=user.name,
        dept=user.dept,
        contact=user.contact,
        is_admin=user.is_admin,
        theme=user.theme or "white",
        depts=[
            MyDeptOut(
                code=row.dept_code,
                name=names.get(row.dept_code, row.dept_code),
                role=row.role,
                can_manage=row.role == DeptRole.manager or user.is_admin,
            )
            for row in rows
        ],
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

    if payload.dept_code:
        if dept_service.get_department(db, payload.dept_code) is None:
            raise HTTPException(404, f"그런 부서가 없습니다: {payload.dept_code}")
        dept_service.join(db, payload.dept_code, user.user_id, payload.dept_role)
    else:
        dept_service.sync_from_profile(db, user)
    return _me(db, user)
