"""앱 의견(VOC) - 써 본 사람이 남기고, 앱을 올린 사람이 답합니다.

왜 필요한가
  앱스토어에 앱이 쌓이면 "이 앱 이거 안 되던데요"가 복도에서 오갑니다.
  그 말이 앱을 올린 사람에게 닿지 않으면 앱은 고쳐지지 않고, 사람들은
  그 앱을 조용히 안 쓰게 됩니다. 의견을 앱 옆에 붙여 두고 등록자에게
  알림으로 보내는 게 이 파일의 전부입니다.

흐름
  사용자가 의견 -> 등록자에게 알림 -> 등록자가 상태를 옮기고 답변
  -> 의견 쓴 사람에게 다시 알림
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app import notify
from app.api.apps import _visible_or_404  # 앱이 보이는 조건은 한 곳에만 둡니다
from app.audit import record
from app.db import get_db
from app.deps import current_user, is_admin
from app.models import AppFeedback, User, VocStatus
from app.schemas import VocIn, VocOut, VocReplyIn

router = APIRouter(tags=["앱 의견"])

KIND_LABEL = {"bug": "잘 안 됨", "idea": "개선 요청", "question": "문의"}
STATUS_LABEL = {
    "open": "접수",
    "in_progress": "확인 중",
    "done": "처리 완료",
    "wontfix": "안 고치기로 함",
}


def _can_answer(voc: AppFeedback, user_id: str) -> bool:
    """답변과 상태 변경은 앱을 올린 사람과 관리자만."""
    return voc.owner_user_id == user_id or is_admin(user_id)


# ------------------------------ 앱에 의견 남기기 ------------------------------
@router.post(
    "/api/apps/{app_id}/voc", response_model=VocOut, status_code=201,
    summary="이 앱에 의견 남기기",
)
def create_voc(
    app_id: str,
    payload: VocIn,
    request: Request,
    db: Session = Depends(get_db),
    user_id: str = Depends(current_user),
) -> AppFeedback:
    app = _visible_or_404(db, app_id, user_id)
    author = db.query(User).filter(User.user_id == user_id).first()

    voc = AppFeedback(
        app_id=app.id,
        app_name=app.name,
        owner_user_id=app.owner_user_id,
        user_id=user_id,
        user_name=author.name if author else "",
        kind=payload.kind,
        rating=payload.rating,
        title=payload.title.strip(),
        body=payload.body,
        run_id=payload.run_id,
        # 지금 돌고 있는 버전을 같이 적어 둡니다. 나중에 등록자가
        # "그건 v1.1 에서 고쳤습니다" 라고 답할 수 있어야 하니까요.
        app_version=app.package_version,
    )
    db.add(voc)
    db.commit()
    db.refresh(voc)

    if app.owner_user_id and app.owner_user_id != user_id:
        notify.send(
            db,
            app.owner_user_id,
            "voc_new",
            f"'{app.name}' 앱에 의견이 왔습니다",
            f"[{KIND_LABEL.get(payload.kind.value, '의견')}] {voc.title}\n"
            f"보낸 사람: {voc.user_name or user_id}",
            target_id=voc.id,
        )
    record(db, user_id, "voc_created", "app", app.id,
           {"voc_id": voc.id, "kind": voc.kind.value}, request)
    return voc


@router.get("/api/apps/{app_id}/voc", response_model=list[VocOut], summary="이 앱에 온 의견")
def list_app_voc(
    app_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(current_user),
) -> list[AppFeedback]:
    """앱을 볼 수 있는 사람은 남이 쓴 의견도 봅니다.

    같은 제보가 여러 번 올라오는 걸 줄이고, "이건 이미 고치는 중"이라는
    답변이 모두에게 보이게 하려는 것입니다.
    """
    app = _visible_or_404(db, app_id, user_id)
    return (
        db.query(AppFeedback)
        .filter(AppFeedback.app_id == app.id)
        .order_by(AppFeedback.created_at.desc())
        .all()
    )


# ------------------------------ 내 의견함 ------------------------------
@router.get("/api/voc/inbox", response_model=list[VocOut], summary="내 앱에 온 의견(등록자)")
def inbox(
    open_only: bool = Query(default=False, description="아직 안 끝난 것만"),
    db: Session = Depends(get_db),
    user_id: str = Depends(current_user),
) -> list[AppFeedback]:
    query = db.query(AppFeedback).filter(AppFeedback.owner_user_id == user_id)
    if open_only:
        query = query.filter(
            AppFeedback.status.in_([VocStatus.open, VocStatus.in_progress])
        )
    return query.order_by(AppFeedback.created_at.desc()).all()


@router.get("/api/voc/sent", response_model=list[VocOut], summary="내가 보낸 의견")
def sent(
    db: Session = Depends(get_db), user_id: str = Depends(current_user)
) -> list[AppFeedback]:
    return (
        db.query(AppFeedback)
        .filter(AppFeedback.user_id == user_id)
        .order_by(AppFeedback.created_at.desc())
        .all()
    )


@router.get("/api/voc/counts", summary="앱별 의견 수")
def counts(db: Session = Depends(get_db), _: str = Depends(current_user)) -> dict:
    """앱스토어 목록에 «의견 3» 을 붙이려고 한 번에 세어 옵니다.

    사용자가 100명 규모라 파이썬에서 세도 충분히 빠릅니다(앱 순위와 같은 판단).
    """
    rows: dict[str, dict] = {}
    for voc in db.query(AppFeedback).all():
        row = rows.setdefault(
            voc.app_id, {"total": 0, "open": 0, "rating_sum": 0, "rating_count": 0}
        )
        row["total"] += 1
        if voc.status in (VocStatus.open, VocStatus.in_progress):
            row["open"] += 1
        if voc.rating:
            row["rating_sum"] += voc.rating
            row["rating_count"] += 1
    for row in rows.values():
        row["rating"] = (
            round(row.pop("rating_sum") / row["rating_count"], 1)
            if row["rating_count"]
            else 0
        )
    return rows


# ------------------------------ 답변하기 ------------------------------
@router.patch("/api/voc/{voc_id}", response_model=VocOut, summary="답변·상태 바꾸기(등록자)")
def answer(
    voc_id: str,
    payload: VocReplyIn,
    request: Request,
    db: Session = Depends(get_db),
    user_id: str = Depends(current_user),
) -> AppFeedback:
    voc = db.get(AppFeedback, voc_id)
    if voc is None:
        raise HTTPException(404, "의견을 찾을 수 없습니다.")
    if not _can_answer(voc, user_id):
        raise HTTPException(403, "이 앱을 올린 사람만 답변할 수 있습니다.")

    changes = payload.model_dump(exclude_unset=True)
    if "status" in changes and changes["status"] is not None:
        voc.status = changes["status"]
    if changes.get("reply") is not None:
        voc.reply = changes["reply"]
        voc.replied_by = user_id
        voc.replied_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(voc)

    if voc.user_id != user_id:
        notify.send(
            db,
            voc.user_id,
            "voc_answered",
            f"'{voc.app_name}' 의견에 답이 왔습니다",
            f"[{STATUS_LABEL.get(voc.status.value, voc.status.value)}] {voc.title}\n"
            f"{voc.reply}".strip(),
            target_id=voc.id,
        )
    record(db, user_id, "voc_answered", "app", voc.app_id,
           {"voc_id": voc.id, "status": voc.status.value}, request)
    return voc


@router.delete("/api/voc/{voc_id}", status_code=204, response_model=None,
               summary="내가 쓴 의견 지우기")
def delete_voc(
    voc_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(current_user),
) -> None:
    """잘못 올린 의견은 쓴 사람이 지웁니다(등록자는 지우지 못하고 답만 답니다).

    등록자가 마음에 안 드는 제보를 지워 버릴 수 있으면 의견함이 의미가 없습니다.
    """
    voc = db.get(AppFeedback, voc_id)
    if voc is None:
        raise HTTPException(404, "의견을 찾을 수 없습니다.")
    if voc.user_id != user_id and not is_admin(user_id):
        raise HTTPException(403, "내가 쓴 의견만 지울 수 있습니다.")
    db.delete(voc)
    db.commit()
