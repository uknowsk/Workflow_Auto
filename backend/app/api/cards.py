"""에이전트 카드 API - 개인 계정에 저장되는 '자주 쓰는 에이전트'."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import current_user
from app.models import AgentCard
from app.schemas import AgentCardIn, AgentCardOut

router = APIRouter(prefix="/api/cards", tags=["에이전트 카드"])


@router.get("", response_model=list[AgentCardOut], summary="내 카드 목록")
def list_cards(
    db: Session = Depends(get_db), user_id: str = Depends(current_user)
) -> list[AgentCard]:
    return (
        db.query(AgentCard)
        .filter(AgentCard.user_id == user_id)
        .order_by(AgentCard.pinned.desc(), AgentCard.position, AgentCard.created_at)
        .all()
    )


@router.post("", response_model=AgentCardOut, status_code=201, summary="카드 만들기")
def create_card(
    payload: AgentCardIn,
    db: Session = Depends(get_db),
    user_id: str = Depends(current_user),
) -> AgentCard:
    card = AgentCard(user_id=user_id, **payload.model_dump())
    db.add(card)
    db.commit()
    db.refresh(card)
    return card


def _owned(db: Session, card_id: str, user_id: str) -> AgentCard:
    card = db.get(AgentCard, card_id)
    if card is None or card.user_id != user_id:
        raise HTTPException(404, "카드를 찾을 수 없습니다.")
    return card


@router.put("/{card_id}", response_model=AgentCardOut, summary="카드 수정")
def update_card(
    card_id: str,
    payload: AgentCardIn,
    db: Session = Depends(get_db),
    user_id: str = Depends(current_user),
) -> AgentCard:
    card = _owned(db, card_id, user_id)
    for key, value in payload.model_dump().items():
        setattr(card, key, value)
    db.commit()
    db.refresh(card)
    return card


@router.delete("/{card_id}", status_code=204, summary="카드 삭제")
def delete_card(
    card_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(current_user),
) -> None:
    db.delete(_owned(db, card_id, user_id))
    db.commit()
