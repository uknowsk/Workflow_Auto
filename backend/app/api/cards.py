"""에이전트 카드 API.

카드는 두 가지입니다.
  개인 카드     dept_code 가 비어 있음. 만든 사람만 보고 고칩니다.
  부서 공통 카드 dept_code 에 부서 코드가 있음. 그 부서에 묶인 사람 전원에게
                 같이 보이고, 고치는 것은 부서 담당자(manager)와 관리자뿐입니다.

한 화면에 섞어서 내려보냅니다. 화면은 `dept_code` 가 있는지로 구분하고,
`editable` 이 false 면 고치기·지우기 버튼을 숨깁니다.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import departments as dept_service
from app.db import get_db
from app.deps import current_user, is_admin
from app.models import AgentCard
from app.schemas import AgentCardIn, AgentCardOut

router = APIRouter(prefix="/api/cards", tags=["에이전트 카드"])


def _can_edit(db: Session, card: AgentCard, user_id: str) -> bool:
    if card.dept_code:
        return is_admin(user_id, db) or dept_service.is_manager(db, user_id, card.dept_code)
    return card.user_id == user_id


def _out(db: Session, card: AgentCard, user_id: str, names: dict[str, str]) -> AgentCardOut:
    return AgentCardOut(
        id=card.id,
        user_id=card.user_id,
        dept_code=card.dept_code,
        dept_name=names.get(card.dept_code, card.dept_code),
        editable=_can_edit(db, card, user_id),
        title=card.title,
        description=card.description,
        icon=card.icon,
        prompt_template=card.prompt_template,
        app_ids=card.app_ids or [],
        recipe_id=card.recipe_id,
        position=card.position,
        pinned=card.pinned,
    )


@router.get("", response_model=list[AgentCardOut], summary="내 카드 + 부서 공통 카드")
def list_cards(
    db: Session = Depends(get_db), user_id: str = Depends(current_user)
) -> list[AgentCardOut]:
    my_codes = dept_service.my_dept_codes(db, user_id)

    mine = (
        db.query(AgentCard)
        .filter(AgentCard.user_id == user_id, AgentCard.dept_code == "")
        .all()
    )
    shared = (
        db.query(AgentCard).filter(AgentCard.dept_code.in_(my_codes)).all()
        if my_codes
        else []
    )

    names = dept_service.dept_names(db, my_codes)
    # 부서 공통 카드를 위에 두고, 그다음 고정 카드, 그다음 저장 순서.
    cards = sorted(
        shared + mine,
        key=lambda c: (0 if c.dept_code else 1, not c.pinned, c.position, c.created_at),
    )
    return [_out(db, card, user_id, names) for card in cards]


@router.post("", response_model=AgentCardOut, status_code=201, summary="카드 만들기")
def create_card(
    payload: AgentCardIn,
    db: Session = Depends(get_db),
    user_id: str = Depends(current_user),
) -> AgentCardOut:
    data = payload.model_dump()
    dept_code = (data.get("dept_code") or "").strip()
    if dept_code:
        if dept_service.get_department(db, dept_code) is None:
            raise HTTPException(404, f"그런 부서가 없습니다: {dept_code}")
        if not (is_admin(user_id, db) or dept_service.is_manager(db, user_id, dept_code)):
            raise HTTPException(
                403, "부서 공통 카드는 그 부서의 담당자나 관리자만 만들 수 있습니다."
            )
    data["dept_code"] = dept_code

    card = AgentCard(user_id=user_id, **data)
    db.add(card)
    db.commit()
    db.refresh(card)
    return _out(db, card, user_id, dept_service.dept_names(db, [dept_code] if dept_code else []))


def _editable_or_403(db: Session, card_id: str, user_id: str) -> AgentCard:
    card = db.get(AgentCard, card_id)
    if card is None:
        raise HTTPException(404, "카드를 찾을 수 없습니다.")
    if card.dept_code:
        # 부서 밖 사람에게는 있다는 사실도 알리지 않습니다.
        if not (
            is_admin(user_id, db) or dept_service.is_member(db, user_id, card.dept_code)
        ):
            raise HTTPException(404, "카드를 찾을 수 없습니다.")
        if not _can_edit(db, card, user_id):
            raise HTTPException(
                403, "부서 공통 카드는 그 부서의 담당자나 관리자만 고칠 수 있습니다."
            )
        return card
    if card.user_id != user_id:
        raise HTTPException(404, "카드를 찾을 수 없습니다.")
    return card


@router.put("/{card_id}", response_model=AgentCardOut, summary="카드 수정")
def update_card(
    card_id: str,
    payload: AgentCardIn,
    db: Session = Depends(get_db),
    user_id: str = Depends(current_user),
) -> AgentCardOut:
    card = _editable_or_403(db, card_id, user_id)
    changes = payload.model_dump()
    # 카드의 소속(개인/부서)은 수정으로 바꾸지 않습니다. 옮기려면 지우고 다시 만듭니다.
    changes.pop("dept_code", None)
    for key, value in changes.items():
        setattr(card, key, value)
    db.commit()
    db.refresh(card)
    return _out(db, card, user_id, dept_service.dept_names(db, [card.dept_code]))


@router.delete("/{card_id}", status_code=204, response_model=None,
               summary="카드 삭제")
def delete_card(
    card_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(current_user),
) -> None:
    db.delete(_editable_or_403(db, card_id, user_id))
    db.commit()
