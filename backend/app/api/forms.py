"""양식 저장소 - 결과물을 채워 넣을 틀을 중앙 서버에 보관합니다.

예) 주간보고.xlsx, 출장보고서.docx, 회의록 틀.md

텍스트 양식(.md/.txt)은 본문을 그대로 읽어 두었다가 오케스트레이터가
"이 틀에 맞춰 써라"라고 시킬 때 씁니다. 엑셀·워드 같은 이진 파일은
지금은 보관과 내려받기까지만 하고, 자동 채우기는 다음 단계입니다.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.audit import record
from app.config import get_settings
from app.db import get_db
from app.deps import current_user, is_admin
from app.models import FormTemplate

router = APIRouter(prefix="/api/forms", tags=["양식 저장소"])
settings = get_settings()

TEXT_SUFFIXES = {".md", ".txt", ".csv", ".json", ".html"}
MAX_BYTES = 20 * 1024 * 1024


def forms_root() -> Path:
    path = Path(settings.data_dir) / "forms"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _out(form: FormTemplate) -> dict:
    return {
        "id": form.id,
        "name": form.name,
        "description": form.description,
        "category": form.category,
        "filename": form.filename,
        "size_bytes": form.size_bytes,
        "is_text": bool(form.text_body),
        "uploaded_by": form.uploaded_by,
        "created_at": form.created_at.isoformat() if form.created_at else "",
    }


@router.get("", summary="양식 목록")
def list_forms(
    db: Session = Depends(get_db),
    _: str = Depends(current_user),
    category: str | None = None,
) -> list[dict]:
    query = db.query(FormTemplate)
    if category:
        query = query.filter(FormTemplate.category == category)
    return [_out(f) for f in query.order_by(FormTemplate.name).all()]


@router.post("", status_code=201, summary="양식 올리기")
async def upload_form(
    request: Request,
    name: str = Form(...),
    description: str = Form(""),
    category: str = Form("etc"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user_id: str = Depends(current_user),
) -> dict:
    form = FormTemplate(
        name=name,
        description=description,
        category=category,
        filename=Path(file.filename or "form").name,  # 경로가 섞여 들어오는 것 방지
        content_type=file.content_type or "application/octet-stream",
        uploaded_by=user_id,
    )
    db.add(form)
    db.flush()

    destination = forms_root() / f"{form.id}_{form.filename}"
    with destination.open("wb") as out:
        shutil.copyfileobj(file.file, out, length=1024 * 1024)

    size = destination.stat().st_size
    if size > MAX_BYTES:
        destination.unlink(missing_ok=True)
        db.rollback()
        raise HTTPException(400, "파일이 너무 큽니다(최대 20MB).")

    form.stored_path = str(destination)
    form.size_bytes = size
    if destination.suffix.lower() in TEXT_SUFFIXES:
        try:
            form.text_body = destination.read_text(encoding="utf-8")[:20000]
        except UnicodeDecodeError:
            form.text_body = ""

    db.commit()
    db.refresh(form)
    record(db, user_id, "form_uploaded", "form", form.id, {"name": name}, request)
    return _out(form)


@router.get("/{form_id}/download", summary="양식 내려받기")
def download_form(
    form_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user_id: str = Depends(current_user),
) -> FileResponse:
    form = db.get(FormTemplate, form_id)
    if form is None or not Path(form.stored_path).is_file():
        raise HTTPException(404, "양식을 찾을 수 없습니다.")
    record(db, user_id, "form_downloaded", "form", form.id, {"name": form.name}, request)
    return FileResponse(
        form.stored_path, filename=form.filename, media_type=form.content_type
    )


@router.delete("/{form_id}", status_code=204, summary="양식 삭제")
def delete_form(
    form_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user_id: str = Depends(current_user),
) -> None:
    form = db.get(FormTemplate, form_id)
    if form is None:
        raise HTTPException(404, "양식을 찾을 수 없습니다.")
    if form.uploaded_by != user_id and not is_admin(user_id):
        raise HTTPException(403, "올린 사람만 지울 수 있습니다.")

    Path(form.stored_path).unlink(missing_ok=True)
    db.delete(form)
    db.commit()
    record(db, user_id, "form_deleted", "form", form_id, {"name": form.name}, request)
