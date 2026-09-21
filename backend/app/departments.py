"""부서 묶음을 다루는 곳. "같은 부서인가?"를 묻는 곳은 전부 여기를 거칩니다.

왜 한 파일에 모았나: 부서 판정이 여기저기 흩어지면 한 군데만 고치고 다른 데를
잊었을 때 남의 부서 앱이 보이는 사고가 납니다. 판정은 이 파일에만 둡니다.

기억할 규칙 세 가지
  1. 같은 부서인지는 dept_members 표로만 따집니다(User.dept 글자는 화면 표시용).
  2. 부서 공통 앱/카드를 만들고 고치는 것은 그 부서의 담당자(manager)와 관리자뿐.
  3. 보는 것은 그 부서에 묶인 사람 전원.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Department, DeptMember, DeptRole, User


def my_dept_codes(db: Session, user_id: str) -> list[str]:
    """이 사번이 묶여 있는 부서 코드들. 안 묶여 있으면 빈 목록."""
    if not user_id:
        return []
    rows = db.query(DeptMember.dept_code).filter(DeptMember.user_id == user_id).all()
    return [row[0] for row in rows]


def my_memberships(db: Session, user_id: str) -> list[DeptMember]:
    """이 사번의 부서 묶음 줄들(역할까지 필요할 때)."""
    if not user_id:
        return []
    return db.query(DeptMember).filter(DeptMember.user_id == user_id).all()


def is_member(db: Session, user_id: str, dept_code: str) -> bool:
    if not (user_id and dept_code):
        return False
    return (
        db.query(DeptMember)
        .filter(DeptMember.user_id == user_id, DeptMember.dept_code == dept_code)
        .first()
        is not None
    )


def is_manager(db: Session, user_id: str, dept_code: str) -> bool:
    """부서 공통 앱·카드를 등록/수정할 수 있는 사람인지."""
    if not (user_id and dept_code):
        return False
    row = (
        db.query(DeptMember)
        .filter(DeptMember.user_id == user_id, DeptMember.dept_code == dept_code)
        .first()
    )
    return row is not None and row.role == DeptRole.manager


def get_department(db: Session, dept_code: str) -> Department | None:
    return db.query(Department).filter(Department.code == dept_code).first()


def dept_names(db: Session, codes: list[str]) -> dict[str, str]:
    """코드 -> 부서 이름. 화면에 코드 대신 이름을 보여 주려고 씁니다."""
    if not codes:
        return {}
    rows = db.query(Department).filter(Department.code.in_(codes)).all()
    return {row.code: row.name for row in rows}


def join(
    db: Session, dept_code: str, user_id: str, role: DeptRole = DeptRole.member
) -> DeptMember:
    """부서원으로 넣습니다. 이미 있으면 역할만 맞춰 줍니다."""
    row = (
        db.query(DeptMember)
        .filter(DeptMember.dept_code == dept_code, DeptMember.user_id == user_id)
        .first()
    )
    if row is None:
        row = DeptMember(dept_code=dept_code, user_id=user_id, role=role)
        db.add(row)
    else:
        row.role = role
    db.commit()
    db.refresh(row)
    return row


def leave(db: Session, dept_code: str, user_id: str) -> None:
    db.query(DeptMember).filter(
        DeptMember.dept_code == dept_code, DeptMember.user_id == user_id
    ).delete()
    db.commit()


def sync_from_profile(db: Session, user: User) -> None:
    """계정에 적힌 소속 글자가 부서 표의 코드나 이름과 똑같으면 자동으로 묶어 줍니다.

    사내 SSO 가 부서를 내려주기 전까지 쓰는 다리입니다. 글자가 정확히 같을 때만
    묶습니다 — 비슷해 보인다고 묶으면 남의 부서 앱이 보이게 되니까요.
    묶인 적이 한 번이라도 있으면(이미 부서가 있으면) 건드리지 않습니다.
    관리자가 명단에서 옮긴 사람을 로그인할 때마다 되돌리면 안 되기 때문입니다.
    """
    raw = (user.dept or "").strip()
    if not raw or my_dept_codes(db, user.user_id):
        return
    target = (
        db.query(Department)
        .filter(Department.is_active.is_(True))
        .filter((Department.code == raw) | (Department.name == raw))
        .first()
    )
    if target is not None:
        join(db, target.code, user.user_id)
