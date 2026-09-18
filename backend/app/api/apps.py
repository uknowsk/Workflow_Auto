"""앱스토어 API - 개발자가 감싼 앱을 등록하고 목록을 봅니다."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.deps import current_user, is_admin, require_admin
from app.mcp_client import client as mcp
from app.models import AgentCard, App, AppStatus, AppTool, AppVisibility
from app.schemas import AppOut, AppRegisterIn, AppUpdateIn

router = APIRouter(prefix="/api/apps", tags=["앱스토어"])
settings = get_settings()


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
    elif not is_admin(user_id):
        # 공식 승인된 앱 + 내가 올린 앱만 보입니다. 남의 개인용 앱은 안 보입니다.
        query = query.filter(
            (App.visibility == AppVisibility.approved) | (App.owner_user_id == user_id)
        )

    if category:
        query = query.filter(App.category == category)
    if q:
        like = f"%{q}%"
        query = query.filter(App.name.ilike(like) | App.description.ilike(like))
    return query.order_by(App.created_at.desc()).all()


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
    if (
        app.visibility != AppVisibility.approved
        and app.owner_user_id != user_id
        and not is_admin(user_id)
    ):
        raise HTTPException(404, "앱을 찾을 수 없습니다.")
    return app


def _owned_or_403(db: Session, app_id: str, user_id: str) -> App:
    """수정/삭제는 올린 본인이나 관리자만."""
    app = db.get(App, app_id)
    if app is None:
        raise HTTPException(404, "앱을 찾을 수 없습니다.")
    if app.owner_user_id != user_id and not is_admin(user_id):
        raise HTTPException(403, "이 앱을 올린 사람만 수정할 수 있습니다.")
    return app


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


@router.get("/{app_id}", response_model=AppOut, summary="앱 상세")
def get_app(
    app_id: str, db: Session = Depends(get_db), user_id: str = Depends(current_user)
) -> App:
    return _visible_or_404(db, app_id, user_id)


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
    if data["visibility"] == AppVisibility.approved and not is_admin(user_id):
        data["visibility"] = AppVisibility.pending

    app = App(owner_user_id=user_id, **data)
    db.add(app)
    db.commit()
    db.refresh(app)
    await _sync_tools(db, app)  # 등록 즉시 기능 목록을 읽어옵니다
    return app


@router.patch("/{app_id}", response_model=AppOut, summary="앱 수정")
async def update_app(
    app_id: str,
    payload: AppUpdateIn,
    db: Session = Depends(get_db),
    user_id: str = Depends(current_user),
) -> App:
    app = _owned_or_403(db, app_id, user_id)

    changes = payload.model_dump(exclude_unset=True)
    for key, value in changes.items():
        setattr(app, key, value)
    db.commit()
    db.refresh(app)

    if "endpoint" in changes:  # 주소가 바뀌면 기능 목록도 다시 읽습니다
        await _sync_tools(db, app)
    return app


@router.post("/{app_id}/refresh", response_model=AppOut, summary="기능 목록 새로고침")
async def refresh_app(
    app_id: str, db: Session = Depends(get_db), user_id: str = Depends(current_user)
) -> App:
    app = _owned_or_403(db, app_id, user_id)
    await _sync_tools(db, app)
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
