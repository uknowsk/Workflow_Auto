"""도구 서랍이 쓰는 작은 저장소 - 메모와 그림.

계산기·단위 변환·세계 시계처럼 계산만 하는 도구는 브라우저 안에서 끝나서
서버가 필요 없습니다. 여기 있는 것은 "다음에 다시 열어봐야 하는 것"뿐입니다.
같은 사람이 회사 PC 와 집에서 열어도 같은 것이 보이도록 계정에 붙여 둡니다.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import current_user
from app.models import Drawing, ToolNote
from app.schemas import DrawingFull, DrawingIn, DrawingOut, NoteIn, NoteOut

router = APIRouter(prefix="/api/tools", tags=["도구 서랍"])

# 그림 한 장의 최대 크기. A4 정도를 꽉 채워 그려도 2MB 를 넘기 어렵습니다.
MAX_DRAWING_BYTES = 6 * 1024 * 1024
# 한 사람이 쌓아 둘 수 있는 장수. 넘으면 오래된 것부터 지우라고 알려 줍니다.
MAX_DRAWINGS_PER_USER = 100
MAX_NOTES_PER_USER = 200


# ------------------------------- 메모 -------------------------------
@router.get("/notes", response_model=list[NoteOut], summary="내 메모 목록")
def list_notes(
    db: Session = Depends(get_db), user_id: str = Depends(current_user)
) -> list[ToolNote]:
    return (
        db.query(ToolNote)
        .filter(ToolNote.user_id == user_id)
        .order_by(ToolNote.pinned.desc(), ToolNote.updated_at.desc())
        .all()
    )


@router.post("/notes", response_model=NoteOut, status_code=201, summary="메모 저장")
def create_note(
    payload: NoteIn,
    db: Session = Depends(get_db),
    user_id: str = Depends(current_user),
) -> ToolNote:
    count = db.query(ToolNote).filter(ToolNote.user_id == user_id).count()
    if count >= MAX_NOTES_PER_USER:
        raise HTTPException(
            400, f"메모는 {MAX_NOTES_PER_USER}장까지 저장할 수 있습니다. 필요 없는 메모를 지워 주세요."
        )
    note = ToolNote(user_id=user_id, **payload.model_dump())
    db.add(note)
    db.commit()
    db.refresh(note)
    return note


def _my_note(db: Session, note_id: str, user_id: str) -> ToolNote:
    note = db.get(ToolNote, note_id)
    if note is None or note.user_id != user_id:
        raise HTTPException(404, "메모를 찾을 수 없습니다.")
    return note


@router.put("/notes/{note_id}", response_model=NoteOut, summary="메모 고치기")
def update_note(
    note_id: str,
    payload: NoteIn,
    db: Session = Depends(get_db),
    user_id: str = Depends(current_user),
) -> ToolNote:
    note = _my_note(db, note_id, user_id)
    for key, value in payload.model_dump().items():
        setattr(note, key, value)
    db.commit()
    db.refresh(note)
    return note


@router.delete("/notes/{note_id}", status_code=204, response_model=None,
               summary="메모 지우기")
def delete_note(
    note_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(current_user),
) -> None:
    db.delete(_my_note(db, note_id, user_id))
    db.commit()


# ------------------------------- 그림 -------------------------------
@router.get("/drawings", response_model=list[DrawingOut], summary="내 그림 목록")
def list_drawings(
    db: Session = Depends(get_db), user_id: str = Depends(current_user)
) -> list[Drawing]:
    return (
        db.query(Drawing)
        .filter(Drawing.user_id == user_id)
        .order_by(Drawing.updated_at.desc())
        .all()
    )


@router.get("/drawings/{drawing_id}", response_model=DrawingFull, summary="그림 하나 불러오기")
def get_drawing(
    drawing_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(current_user),
) -> Drawing:
    return _my_drawing(db, drawing_id, user_id)


def _check_image(image: str) -> None:
    if not image.startswith("data:image/png;base64,"):
        raise HTTPException(400, "PNG 그림만 저장할 수 있습니다.")
    if len(image.encode("utf-8")) > MAX_DRAWING_BYTES:
        raise HTTPException(
            400, "그림이 너무 큽니다. 캔버스를 조금 줄이거나 나눠서 저장해 주세요."
        )


@router.post("/drawings", response_model=DrawingOut, status_code=201, summary="그림 저장")
def create_drawing(
    payload: DrawingIn,
    db: Session = Depends(get_db),
    user_id: str = Depends(current_user),
) -> Drawing:
    _check_image(payload.image)
    count = db.query(Drawing).filter(Drawing.user_id == user_id).count()
    if count >= MAX_DRAWINGS_PER_USER:
        raise HTTPException(
            400, f"그림은 {MAX_DRAWINGS_PER_USER}장까지 저장할 수 있습니다. 오래된 그림을 지워 주세요."
        )
    drawing = Drawing(user_id=user_id, **payload.model_dump())
    db.add(drawing)
    db.commit()
    db.refresh(drawing)
    return drawing


def _my_drawing(db: Session, drawing_id: str, user_id: str) -> Drawing:
    drawing = db.get(Drawing, drawing_id)
    if drawing is None or drawing.user_id != user_id:
        raise HTTPException(404, "그림을 찾을 수 없습니다.")
    return drawing


@router.put("/drawings/{drawing_id}", response_model=DrawingOut, summary="그림 덮어쓰기")
def update_drawing(
    drawing_id: str,
    payload: DrawingIn,
    db: Session = Depends(get_db),
    user_id: str = Depends(current_user),
) -> Drawing:
    _check_image(payload.image)
    drawing = _my_drawing(db, drawing_id, user_id)
    for key, value in payload.model_dump().items():
        setattr(drawing, key, value)
    db.commit()
    db.refresh(drawing)
    return drawing


@router.delete("/drawings/{drawing_id}", status_code=204, response_model=None,
               summary="그림 지우기")
def delete_drawing(
    drawing_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(current_user),
) -> None:
    db.delete(_my_drawing(db, drawing_id, user_id))
    db.commit()
