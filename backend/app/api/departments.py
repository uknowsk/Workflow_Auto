"""부서 API - 부서를 만들고, 누가 그 부서원인지 묶습니다.

부서 공통 앱과 부서 공통 카드가 "부서원 전원에게 보이는" 근거가 이 명단입니다.
  - 부서 만들기/지우기        : 관리자
  - 부서원 넣기/빼기/담당자 지정 : 관리자 또는 그 부서의 담당자
  - 내 부서 보기              : 누구나(자기 것만)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app import departments as dept_service
from app.audit import record
from app.db import get_db
from app.deps import current_user, is_admin, require_admin
from app.models import AgentCard, App, AppVisibility, Department, DeptMember, DeptRole, User
from app.schemas import (
    DepartmentIn,
    DepartmentOut,
    DepartmentUpdateIn,
    DeptMemberIn,
    DeptMemberOut,
    MyDeptOut,
)

router = APIRouter(prefix="/api/departments", tags=["부서"])


def _dept_or_404(db: Session, code: str) -> Department:
    dept = dept_service.get_department(db, code)
    if dept is None:
        raise HTTPException(404, f"그런 부서가 없습니다: {code}")
    return dept


def _require_manage(db: Session, user_id: str, code: str) -> None:
    if not (is_admin(user_id, db) or dept_service.is_manager(db, user_id, code)):
        raise HTTPException(403, "그 부서의 담당자나 관리자만 할 수 있습니다.")


def _out(db: Session, dept: Department) -> DepartmentOut:
    members = db.query(DeptMember).filter(DeptMember.dept_code == dept.code).count()
    apps = (
        db.query(App)
        .filter(
            App.owner_dept_code == dept.code,
            App.visibility == AppVisibility.department,
        )
        .count()
    )
    cards = db.query(AgentCard).filter(AgentCard.dept_code == dept.code).count()
    return DepartmentOut(
        code=dept.code,
        name=dept.name,
        description=dept.description,
        is_active=dept.is_active,
        member_count=members,
        app_count=apps,
        card_count=cards,
    )


@router.get("", response_model=list[DepartmentOut], summary="부서 목록")
def list_departments(
    db: Session = Depends(get_db), _: str = Depends(current_user)
) -> list[DepartmentOut]:
    """부서 이름은 앱 등록 화면에서 고르게 해야 하므로 누구나 볼 수 있습니다."""
    rows = db.query(Department).order_by(Department.name).all()
    return [_out(db, row) for row in rows]


@router.get("/mine", response_model=list[MyDeptOut], summary="내가 묶인 부서")
def my_departments(
    db: Session = Depends(get_db), user_id: str = Depends(current_user)
) -> list[MyDeptOut]:
    rows = db.query(DeptMember).filter(DeptMember.user_id == user_id).all()
    names = dept_service.dept_names(db, [row.dept_code for row in rows])
    return [
        MyDeptOut(
            code=row.dept_code,
            name=names.get(row.dept_code, row.dept_code),
            role=row.role,
            can_manage=row.role == DeptRole.manager or is_admin(user_id, db),
        )
        for row in rows
    ]


@router.post("", response_model=DepartmentOut, status_code=201, summary="부서 만들기(관리자)")
def create_department(
    payload: DepartmentIn,
    request: Request,
    db: Session = Depends(get_db),
    admin: str = Depends(require_admin),
) -> DepartmentOut:
    if dept_service.get_department(db, payload.code) is not None:
        raise HTTPException(409, f"이미 있는 부서 코드입니다: {payload.code}")
    dept = Department(**payload.model_dump())
    db.add(dept)
    db.commit()
    db.refresh(dept)
    record(db, admin, "dept_created", "department", dept.code, request=request)
    return _out(db, dept)


@router.patch("/{code}", response_model=DepartmentOut, summary="부서 고치기(관리자)")
def update_department(
    code: str,
    payload: DepartmentUpdateIn,
    db: Session = Depends(get_db),
    _: str = Depends(require_admin),
) -> DepartmentOut:
    dept = _dept_or_404(db, code)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(dept, key, value)
    db.commit()
    db.refresh(dept)
    return _out(db, dept)


@router.delete("/{code}", status_code=204, response_model=None, summary="부서 지우기(관리자)")
def delete_department(
    code: str,
    request: Request,
    db: Session = Depends(get_db),
    admin: str = Depends(require_admin),
) -> None:
    """부서 공통 앱이나 카드가 남아 있으면 지우지 않습니다.

    부서를 먼저 지우면 그 앱과 카드가 아무도 손댈 수 없는 상태로 떠돕니다.
    """
    dept = _dept_or_404(db, code)
    summary = _out(db, dept)
    if summary.app_count or summary.card_count:
        raise HTTPException(
            409,
            "부서 공통 앱 "
            f"{summary.app_count}개, 공통 카드 {summary.card_count}개가 남아 있습니다. "
            "먼저 옮기거나 지운 뒤에 부서를 지워 주세요.",
        )
    db.query(DeptMember).filter(DeptMember.dept_code == code).delete()
    db.delete(dept)
    db.commit()
    record(db, admin, "dept_deleted", "department", code, request=request)


@router.get("/{code}/members", response_model=list[DeptMemberOut], summary="부서원 명단")
def list_members(
    code: str, db: Session = Depends(get_db), user_id: str = Depends(current_user)
) -> list[DeptMemberOut]:
    """같은 부서원이거나 관리자면 볼 수 있습니다."""
    _dept_or_404(db, code)
    if not (is_admin(user_id, db) or dept_service.is_member(db, user_id, code)):
        raise HTTPException(403, "그 부서의 부서원만 볼 수 있습니다.")

    rows = db.query(DeptMember).filter(DeptMember.dept_code == code).all()
    profiles = {
        user.user_id: user
        for user in db.query(User)
        .filter(User.user_id.in_([row.user_id for row in rows] or [""]))
        .all()
    }
    return [
        DeptMemberOut(
            user_id=row.user_id,
            name=getattr(profiles.get(row.user_id), "name", ""),
            role=row.role,
        )
        for row in rows
    ]


@router.post(
    "/{code}/members", response_model=DeptMemberOut, status_code=201, summary="부서원 넣기"
)
def add_member(
    code: str,
    payload: DeptMemberIn,
    request: Request,
    db: Session = Depends(get_db),
    user_id: str = Depends(current_user),
) -> DeptMemberOut:
    _dept_or_404(db, code)
    _require_manage(db, user_id, code)
    row = dept_service.join(db, code, payload.user_id, payload.role)
    record(db, user_id, "dept_member_added", "department", code, {"member": payload.user_id},
           request=request)
    profile = db.query(User).filter(User.user_id == payload.user_id).first()
    return DeptMemberOut(
        user_id=row.user_id, name=getattr(profile, "name", ""), role=row.role
    )


@router.delete(
    "/{code}/members/{member_id}", status_code=204, response_model=None, summary="부서원 빼기"
)
def remove_member(
    code: str,
    member_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user_id: str = Depends(current_user),
) -> None:
    _dept_or_404(db, code)
    _require_manage(db, user_id, code)
    dept_service.leave(db, code, member_id)
    record(db, user_id, "dept_member_removed", "department", code, {"member": member_id},
           request=request)
