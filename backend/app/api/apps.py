"""앱스토어 API - 개발자가 감싼 앱을 등록하고 목록을 봅니다."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import departments as dept_service
from app.config import get_settings
from app.db import get_db
from app.deps import current_user, is_admin, require_admin
from app.mcp_client import client as mcp
from app.models import AgentCard, App, AppStatus, AppTool, AppVisibility
from app.api.cards import card_out
from app.schemas import (
    AgentCardOut,
    AppOut,
    AppRegisterIn,
    AppUpdateIn,
    DeptPublishIn,
)

router = APIRouter(prefix="/api/apps", tags=["앱스토어"])
settings = get_settings()


def _visible_filter(db: Session, user_id: str):
    """이 사람에게 보이는 앱의 조건.

      - 관리자가 승인한 공식 앱(approved)
      - 내가 올린 앱
      - 내가 묶인 부서의 부서 공통 앱(department)

    남이 올린 개인용 앱과 남의 부서 앱은 목록에도, 오케스트레이터 후보에도
    들어가지 않습니다. 이 조건은 orchestrator/engine.py 와 같은 규칙입니다.
    """
    condition = (App.visibility == AppVisibility.approved) | (
        App.owner_user_id == user_id
    )
    my_codes = dept_service.my_dept_codes(db, user_id)
    if my_codes:
        condition = condition | (
            (App.visibility == AppVisibility.department)
            & (App.owner_dept_code.in_(my_codes))
        )
    return condition


def _with_dept_name(db: Session, apps: list[App]) -> list[App]:
    """화면에 부서 코드 대신 부서 이름을 보여 주려고 이름을 붙여 둡니다."""
    names = dept_service.dept_names(
        db, [a.owner_dept_code for a in apps if a.owner_dept_code]
    )
    for app in apps:
        app.owner_dept_name = names.get(app.owner_dept_code, "")
    return apps


def _require_dept_manager(db: Session, user_id: str, dept_code: str) -> None:
    if dept_service.get_department(db, dept_code) is None:
        raise HTTPException(404, f"그런 부서가 없습니다: {dept_code}")
    if not (is_admin(user_id, db) or dept_service.is_manager(db, user_id, dept_code)):
        raise HTTPException(
            403, "부서 공통 앱은 그 부서의 담당자나 관리자만 등록할 수 있습니다."
        )


async def _sync_tools(db: Session, app: App) -> None:
    """앱에 접속해 기능 목록을 읽어와 저장합니다(MCP tools/list)."""
    try:
        tools = await mcp.list_tools(
            app.endpoint, headers=app.auth_headers or {}, timeout=settings.mcp_timeout
        )
    except Exception as exc:
        app.status = AppStatus.unreachable
        app.last_error = f"{type(exc).__name__}: {exc}"
        db.commit()
        return

    app.tools.clear()
    db.flush()
    for tool in tools:
        db.add(
            AppTool(
                app_id=app.id,
                name=tool.name,
                description=tool.description,
                input_schema=tool.input_schema,
            )
        )
    app.status = AppStatus.active
    app.last_error = ""
    db.commit()
    db.refresh(app)


@router.get("", response_model=list[AppOut], summary="앱 목록(앱스토어)")
def list_apps(
    db: Session = Depends(get_db),
    user_id: str = Depends(current_user),
    category: str | None = Query(default=None),
    q: str | None = Query(default=None, description="이름/설명 검색어"),
    mine: bool = Query(default=False, description="내가 올린 앱만 보기"),
) -> list[App]:
    query = db.query(App)

    if mine:
        query = query.filter(App.owner_user_id == user_id)
    elif not is_admin(user_id, db):
        query = query.filter(_visible_filter(db, user_id))

    if category:
        query = query.filter(App.category == category)
    if q:
        like = f"%{q}%"
        query = query.filter(App.name.ilike(like) | App.description.ilike(like))
    return _with_dept_name(db, query.order_by(App.created_at.desc()).all())


@router.get("/pending", response_model=list[AppOut], summary="승인 대기 목록(관리자)")
def list_pending(
    db: Session = Depends(get_db), _: str = Depends(require_admin)
) -> list[App]:
    return (
        db.query(App)
        .filter(App.visibility == AppVisibility.pending)
        .order_by(App.created_at)
        .all()
    )


def _visible_or_404(db: Session, app_id: str, user_id: str) -> App:
    app = db.get(App, app_id)
    if app is None:
        raise HTTPException(404, "앱을 찾을 수 없습니다.")
    if is_admin(user_id, db) or app.owner_user_id == user_id:
        return app
    if app.visibility == AppVisibility.approved:
        return app
    if app.visibility == AppVisibility.department and dept_service.is_member(
        db, user_id, app.owner_dept_code
    ):
        return app
    raise HTTPException(404, "앱을 찾을 수 없습니다.")


def _owned_or_403(db: Session, app_id: str, user_id: str) -> App:
    """수정/삭제는 올린 본인, 관리자, 그리고 부서 공통 앱이면 그 부서 담당자.

    부서 담당자를 넣은 이유: 부서 공통 앱을 올린 사람이 부서를 옮기거나 퇴사해도
    부서에 남은 사람이 주소를 고칠 수 있어야 앱이 죽지 않습니다.
    """
    app = db.get(App, app_id)
    if app is None:
        raise HTTPException(404, "앱을 찾을 수 없습니다.")
    if app.owner_user_id == user_id or is_admin(user_id, db):
        return app
    if app.visibility == AppVisibility.department and dept_service.is_manager(
        db, user_id, app.owner_dept_code
    ):
        return app
    raise HTTPException(403, "이 앱을 올린 사람만 수정할 수 있습니다.")


@router.get("/stats/adoption", summary="앱별 카드 등록 인원(관리자)")
def adoption_stats(db: Session = Depends(get_db), _: str = Depends(require_admin)) -> list[dict]:
    """어떤 개인용 앱을 몇 명이 자기 카드에 넣어 쓰는지 셉니다.

    "쓰는 사람이 많은 개인용 앱"이 공식 승인 후보입니다.
    사용자 수가 100명 규모라 파이썬에서 세도 충분히 빠릅니다.
    """
    users_per_app: dict[str, set[str]] = {}
    for card in db.query(AgentCard).all():
        for app_id in card.app_ids or []:
            users_per_app.setdefault(app_id, set()).add(card.user_id)

    rows = []
    for app in db.query(App).all():
        rows.append(
            {
                "app_id": app.id,
                "name": app.name,
                "visibility": app.visibility.value,
                "capability_tag": app.capability_tag,
                "owner_user_id": app.owner_user_id,
                "user_count": len(users_per_app.get(app.id, ())),
            }
        )
    return sorted(rows, key=lambda r: r["user_count"], reverse=True)


# --------------------------- 설치(내 에이전트에 담기) ---------------------------
#
# "설치"는 앱을 어딘가에 복사하는 것이 아닙니다. 앱은 이미 서버에 떠 있고,
# 설치 = **그 앱 하나만 쓰는 내 카드 한 장**을 만드는 일입니다.
# 카드에 담긴 앱은 실행할 때 후보 1순위가 되고(orchestrator/engine.py 의
# pick_apps), 역할이 겹치는 다른 앱을 제치고 그 앱이 쓰입니다.
#
# 그래서 "이 앱이 설치되어 있나"의 기준은 **그 앱 하나만 든 내 개인 카드가
# 있는가** 입니다(여러 앱을 묶어 만든 카드는 사용자가 직접 꾸민 것이므로
# 설치로 세지도, 빼기로 지우지도 않습니다).


def _installed_card(db: Session, app_id: str, user_id: str) -> AgentCard | None:
    for card in (
        db.query(AgentCard)
        .filter(AgentCard.user_id == user_id, AgentCard.dept_code == "")
        .order_by(AgentCard.created_at)
        .all()
    ):
        if list(card.app_ids or []) == [app_id]:
            return card
    return None


@router.post(
    "/{app_id}/install",
    response_model=AgentCardOut,
    status_code=201,
    summary="이 앱을 내 에이전트에 담기(설치)",
)
def install_app(
    app_id: str, db: Session = Depends(get_db), user_id: str = Depends(current_user)
) -> AgentCardOut:
    app = _visible_or_404(db, app_id, user_id)

    # 두 번 눌러도 카드가 두 장 생기지 않게, 이미 있으면 그 카드를 그대로 돌려줍니다.
    existing = _installed_card(db, app_id, user_id)
    if existing is not None:
        return card_out(db, existing, user_id)

    card = AgentCard(
        user_id=user_id,
        dept_code="",
        title=app.name,
        description=app.usage_hint or app.description,
        icon=app.icon or "🧩",
        prompt_template="",  # 무엇을 시킬지는 그때그때 다르므로 비워 둡니다.
        app_ids=[app.id],
        pinned=False,
    )
    db.add(card)
    db.commit()
    db.refresh(card)
    return card_out(db, card, user_id)


@router.delete(
    "/{app_id}/install",
    status_code=204,
    response_model=None,
    summary="설치 빼기(내 에이전트에서 카드 지우기)",
)
def uninstall_app(
    app_id: str, db: Session = Depends(get_db), user_id: str = Depends(current_user)
) -> None:
    card = _installed_card(db, app_id, user_id)
    if card is None:
        raise HTTPException(404, "내 에이전트에 담아 둔 앱이 아닙니다.")
    db.delete(card)
    db.commit()


@router.get(
    "/installed/ids",
    response_model=dict[str, str],
    summary="내가 설치한 앱 → 그 앱의 카드 id",
)
def installed_ids(
    db: Session = Depends(get_db), user_id: str = Depends(current_user)
) -> dict[str, str]:
    """앱스토어의 «열기»가 곧장 그 카드로 갈 수 있게 카드 id 까지 같이 줍니다."""
    found: dict[str, str] = {}
    for card in (
        db.query(AgentCard)
        .filter(AgentCard.user_id == user_id, AgentCard.dept_code == "")
        .order_by(AgentCard.created_at)
        .all()
    ):
        app_ids = list(card.app_ids or [])
        if len(app_ids) == 1:
            found.setdefault(app_ids[0], card.id)
    return found


@router.get("/{app_id}", response_model=AppOut, summary="앱 상세")
def get_app(
    app_id: str, db: Session = Depends(get_db), user_id: str = Depends(current_user)
) -> App:
    return _with_dept_name(db, [_visible_or_404(db, app_id, user_id)])[0]


@router.post("", response_model=AppOut, status_code=201, summary="앱 등록")
async def register_app(
    payload: AppRegisterIn,
    db: Session = Depends(get_db),
    user_id: str = Depends(current_user),
) -> App:
    if db.query(App).filter(App.slug == payload.slug).first():
        raise HTTPException(409, f"이미 등록된 slug 입니다: {payload.slug}")

    data = payload.model_dump()
    # 스스로 approved 로 올릴 수는 없습니다. 승인은 관리자만.
    if data["visibility"] == AppVisibility.approved and not is_admin(user_id, db):
        data["visibility"] = AppVisibility.pending

    dept_code = (data.get("owner_dept_code") or "").strip()
    if data["visibility"] == AppVisibility.department:
        if not dept_code:
            raise HTTPException(400, "부서 공통 앱은 어느 부서 것인지 골라야 합니다.")
        _require_dept_manager(db, user_id, dept_code)
    elif dept_code:
        # 부서 공통이 아닌데 부서 코드만 들어온 경우는 오해를 부르니 지웁니다.
        dept_code = ""
    data["owner_dept_code"] = dept_code

    app = App(owner_user_id=user_id, **data)
    db.add(app)
    db.commit()
    db.refresh(app)
    await _sync_tools(db, app)  # 등록 즉시 기능 목록을 읽어옵니다
    return _with_dept_name(db, [app])[0]


@router.patch("/{app_id}", response_model=AppOut, summary="앱 수정")
async def update_app(
    app_id: str,
    payload: AppUpdateIn,
    db: Session = Depends(get_db),
    user_id: str = Depends(current_user),
) -> App:
    app = _owned_or_403(db, app_id, user_id)

    changes = payload.model_dump(exclude_unset=True)
    if "owner_dept_code" in changes and changes["owner_dept_code"] != app.owner_dept_code:
        new_code = (changes["owner_dept_code"] or "").strip()
        if app.visibility == AppVisibility.department and not new_code:
            raise HTTPException(400, "부서 공통 앱에서 부서를 비울 수는 없습니다.")
        if new_code:
            _require_dept_manager(db, user_id, new_code)
        changes["owner_dept_code"] = new_code
    for key, value in changes.items():
        setattr(app, key, value)
    db.commit()
    db.refresh(app)

    if "endpoint" in changes:  # 주소가 바뀌면 기능 목록도 다시 읽습니다
        await _sync_tools(db, app)
    return _with_dept_name(db, [app])[0]


@router.post("/{app_id}/refresh", response_model=AppOut, summary="기능 목록 새로고침")
async def refresh_app(
    app_id: str, db: Session = Depends(get_db), user_id: str = Depends(current_user)
) -> App:
    app = _owned_or_403(db, app_id, user_id)
    await _sync_tools(db, app)
    return app


@router.post("/{app_id}/share-dept", response_model=AppOut, summary="부서 공통으로 내기")
def share_to_dept(
    app_id: str,
    payload: DeptPublishIn,
    db: Session = Depends(get_db),
    user_id: str = Depends(current_user),
) -> App:
    """내 앱을 부서 공통 앱으로 바꿉니다 -> 그 부서에 묶인 사람 전원에게 보입니다."""
    app = _owned_or_403(db, app_id, user_id)
    _require_dept_manager(db, user_id, payload.dept_code)
    app.visibility = AppVisibility.department
    app.owner_dept_code = payload.dept_code
    db.commit()
    db.refresh(app)
    return _with_dept_name(db, [app])[0]


@router.post("/{app_id}/unshare-dept", response_model=AppOut, summary="부서 공통 해제")
def unshare_from_dept(
    app_id: str, db: Session = Depends(get_db), user_id: str = Depends(current_user)
) -> App:
    """부서 공통을 풀고 개인용으로 되돌립니다. 올린 사람은 계속 씁니다."""
    app = _owned_or_403(db, app_id, user_id)
    if app.visibility != AppVisibility.department:
        raise HTTPException(400, "부서 공통 앱이 아닙니다.")
    app.visibility = AppVisibility.private
    app.owner_dept_code = ""
    db.commit()
    db.refresh(app)
    return app


@router.post("/{app_id}/submit", response_model=AppOut, summary="공식 등록 신청")
def submit_app(
    app_id: str, db: Session = Depends(get_db), user_id: str = Depends(current_user)
) -> App:
    """개인용(private) 앱을 '모두가 쓸 수 있게' 신청합니다 -> pending."""
    app = _owned_or_403(db, app_id, user_id)
    app.visibility = AppVisibility.pending
    db.commit()
    db.refresh(app)
    return app


@router.post("/{app_id}/approve", response_model=AppOut, summary="앱 승인(관리자)")
def approve_app(
    app_id: str, db: Session = Depends(get_db), _: str = Depends(require_admin)
) -> App:
    app = db.get(App, app_id)
    if app is None:
        raise HTTPException(404, "앱을 찾을 수 없습니다.")
    app.visibility = AppVisibility.approved
    db.commit()
    db.refresh(app)
    return app


@router.post("/{app_id}/reject", response_model=AppOut, summary="앱 반려(관리자)")
def reject_app(
    app_id: str, db: Session = Depends(get_db), _: str = Depends(require_admin)
) -> App:
    """반려하면 개인용으로 되돌아갑니다. 올린 사람은 계속 쓸 수 있습니다."""
    app = db.get(App, app_id)
    if app is None:
        raise HTTPException(404, "앱을 찾을 수 없습니다.")
    app.visibility = AppVisibility.private
    db.commit()
    db.refresh(app)
    return app


@router.delete("/{app_id}", status_code=204, response_model=None,
               summary="앱 삭제")
def delete_app(
    app_id: str, db: Session = Depends(get_db), user_id: str = Depends(current_user)
) -> None:
    db.delete(_owned_or_403(db, app_id, user_id))
    db.commit()
