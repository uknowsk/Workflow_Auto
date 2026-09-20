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
from app import notify
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


# ──────────────────────────────────────────────────────────────────────────────
# 계정 관리 (관리자)
#
# 여기 있는 세 가지가 "사람이 오고 가는 일"의 전부입니다.
#   목록 보기      : 누가 있고 언제 마지막으로 들어왔는지
#   고치기(PATCH)  : 이름·소속·연락처·관리자 여부·사용 여부·부서 옮기기
#   비밀번호 초기화: 새 비밀번호를 관리자가 정해서 알려 줍니다
#
# 계정을 지우지 않고 '끄는' 이유: 그 사람이 남긴 실행 기록과 감사 기록이
# 주인 없는 줄이 되면 안 되기 때문입니다. 퇴사자는 is_active=false 로 끕니다.
# ──────────────────────────────────────────────────────────────────────────────


class UserRow(BaseModel):
    user_id: str
    name: str
    dept: str
    contact: str
    is_admin: bool
    is_active: bool
    created_at: datetime | None = None
    last_login_at: datetime | None = None
    dept_codes: list[str] = []


class UserPatch(BaseModel):
    """넣은 값만 바꿉니다. 넣지 않은 값은 그대로 둡니다."""

    name: str | None = None
    dept: str | None = Field(None, description="소속(글자). 화면 표시용")
    contact: str | None = None
    is_admin: bool | None = None
    is_active: bool | None = Field(None, description="false 로 두면 로그인이 막힙니다(퇴사자)")
    dept_code: str | None = Field(
        None, description="부서 옮기기. 빈 글자를 넣으면 부서에서 빼기만 합니다"
    )
    dept_role: DeptRole | None = None


class PasswordResetIn(BaseModel):
    password: str = Field(..., min_length=4, description="새 비밀번호")


def _row(db: Session, user: User) -> UserRow:
    return UserRow(
        user_id=user.user_id,
        name=user.name,
        dept=user.dept,
        contact=user.contact,
        is_admin=user.is_admin,
        is_active=user.is_active,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
        dept_codes=dept_service.my_dept_codes(db, user.user_id),
    )


def _find(db: Session, user_id: str) -> User:
    user = db.query(User).filter(User.user_id == user_id).first()
    if user is None:
        raise HTTPException(404, f"그런 사번이 없습니다: {user_id}")
    return user


@router.get("/users", response_model=list[UserRow], summary="계정 목록(관리자)")
def list_users(
    q: str = "",
    include_inactive: bool = True,
    db: Session = Depends(get_db),
    admin: str = Depends(require_admin),
) -> list[UserRow]:
    """사번·이름·소속에 글자가 들어가면 찾아 줍니다. 100명 규모라 전부 내려도 됩니다."""
    query = db.query(User)
    if not include_inactive:
        query = query.filter(User.is_active.is_(True))
    rows = query.order_by(User.created_at.desc()).all()

    needle = q.strip().lower()
    if needle:
        rows = [
            u
            for u in rows
            if needle in u.user_id.lower()
            or needle in (u.name or "").lower()
            or needle in (u.dept or "").lower()
        ]
    return [_row(db, u) for u in rows]


@router.patch("/users/{user_id}", response_model=UserRow, summary="계정 고치기(관리자)")
def update_user(
    user_id: str,
    payload: UserPatch,
    request: Request,
    db: Session = Depends(get_db),
    admin: str = Depends(require_admin),
) -> UserRow:
    user = _find(db, user_id)

    if payload.is_active is False and user.user_id == admin:
        # 자기 계정을 끄면 다시 들어올 방법이 없습니다.
        raise HTTPException(400, "자기 계정은 끌 수 없습니다.")
    if payload.is_admin is False and user.user_id == admin:
        raise HTTPException(400, "자기 관리자 권한은 뗄 수 없습니다.")

    changed: list[str] = []
    for field in ("name", "dept", "contact", "is_admin", "is_active"):
        value = getattr(payload, field)
        if value is not None and getattr(user, field) != value:
            setattr(user, field, value)
            changed.append(field)

    # 부서 옮기기: 지금 묶인 부서에서 모두 빼고 새 부서로 넣습니다.
    if payload.dept_code is not None:
        target = payload.dept_code.strip()
        if target and dept_service.get_department(db, target) is None:
            raise HTTPException(404, f"그런 부서가 없습니다: {target}")
        for code in dept_service.my_dept_codes(db, user.user_id):
            if code != target:
                dept_service.leave(db, code, user.user_id)
        if target:
            dept_service.join(
                db, target, user.user_id, payload.dept_role or DeptRole.member
            )
        changed.append("dept_code")

    db.commit()
    db.refresh(user)
    record(
        db,
        admin,
        "user_updated",
        "user",
        user.user_id,
        detail={"changed": changed},
        request=request,
    )
    return _row(db, user)


@router.post(
    "/users/{user_id}/password",
    response_model=UserRow,
    summary="비밀번호 초기화(관리자)",
)
def reset_password(
    user_id: str,
    payload: PasswordResetIn,
    request: Request,
    db: Session = Depends(get_db),
    admin: str = Depends(require_admin),
) -> UserRow:
    """관리자가 새 비밀번호를 정해 주고, 본인에게 알림 한 줄이 갑니다.

    원문은 저장하지 않으므로 관리자가 직접 알려 줘야 합니다.
    """
    user = _find(db, user_id)
    user.password_hash = hash_password(payload.password)
    db.commit()
    record(db, admin, "password_reset", "user", user.user_id, request=request)
    notify.send(
        db,
        user.user_id,
        kind="password_reset",
        title="비밀번호가 초기화되었습니다",
        body="관리자가 새 비밀번호로 바꿨습니다. 새 비밀번호로 로그인해 주세요.",
        target_id=user.user_id,
    )
    return _row(db, user)
