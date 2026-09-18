"""앱 패키지 등록 - GitHub 주소 또는 ZIP 업로드.

기존의 "이미 돌고 있는 어댑터 주소만 등록"(POST /api/apps)은 그대로 두고,
소스를 통째로 올리는 방식을 여기에 더했습니다.
"""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from app import packages
from app.audit import record
from app.db import get_db
from app.deps import current_user
from app.models import App, AppVisibility, RuntimeLocation, SourceType
from app.schemas import AppOut

router = APIRouter(prefix="/api/apps", tags=["앱스토어"])


def _apply_manifest(app: App, manifest: dict) -> None:
    """매니페스트에 적힌 값으로 앱 정보를 채웁니다(사용자가 적은 값이 우선)."""
    app.name = app.name or manifest.get("name", "")
    app.description = app.description or manifest.get("description", "")
    app.usage_hint = app.usage_hint or manifest.get("usage_hint", "")
    app.category = manifest.get("category", app.category)
    app.capability_tag = app.capability_tag or manifest.get("capability_tag", "")
    app.icon = manifest.get("icon", app.icon)
    app.package_version = str(manifest.get("version", ""))
    if manifest.get("requires_confirmation"):
        app.requires_confirmation = True
    if manifest.get("runtime") in ("server", "pc"):
        app.runtime_location = RuntimeLocation(manifest["runtime"])


def _finish(
    db: Session, app: App, manifest: dict, app_dir: Path, request: Request, user_id: str
) -> App:
    app.package_path = str(app_dir)
    _apply_manifest(app, manifest)
    db.add(app)
    db.commit()
    db.refresh(app)
    record(
        db,
        user_id,
        "app_package_registered",
        "app",
        app.id,
        {"slug": app.slug, "source": app.source_type.value, "runtime": app.runtime_location.value},
        request,
    )
    return app


def _new_app(db: Session, slug: str, user_id: str) -> App:
    if db.query(App).filter(App.slug == slug).first():
        raise HTTPException(409, f"이미 등록된 slug 입니다: {slug}")
    return App(slug=slug, owner_user_id=user_id, visibility=AppVisibility.private)


@router.post("/from-github", response_model=AppOut, status_code=201,
             summary="GitHub 주소로 앱 등록")
def register_from_github(
    request: Request,
    slug: str = Form(..., description="앱 고유 ID. 영문 소문자와 -"),
    source_url: str = Form(..., description="git clone 할 수 있는 주소"),
    ref: str = Form("", description="브랜치나 태그. 비우면 기본 브랜치"),
    runtime: RuntimeLocation = Form(RuntimeLocation.server),
    name: str = Form(""),
    db: Session = Depends(get_db),
    user_id: str = Depends(current_user),
) -> App:
    app = _new_app(db, slug, user_id)
    app.name = name
    app.source_type = SourceType.github
    app.source_url = source_url
    app.runtime_location = runtime

    try:
        app_dir, manifest = packages.store_github(slug, source_url, ref)
    except packages.PackageError as exc:
        raise HTTPException(400, str(exc)) from exc

    return _finish(db, app, manifest, app_dir, request, user_id)


@router.post("/from-zip", response_model=AppOut, status_code=201,
             summary="ZIP 파일로 앱 등록")
async def register_from_zip(
    request: Request,
    slug: str = Form(..., description="앱 고유 ID. 영문 소문자와 -"),
    runtime: RuntimeLocation = Form(RuntimeLocation.server),
    name: str = Form(""),
    file: UploadFile = File(..., description="어댑터 코드를 담은 ZIP"),
    db: Session = Depends(get_db),
    user_id: str = Depends(current_user),
) -> App:
    app = _new_app(db, slug, user_id)
    app.name = name
    app.source_type = SourceType.zip
    app.runtime_location = runtime

    # 업로드 파일을 임시 파일로 받은 뒤 풉니다.
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as temp:
        shutil.copyfileobj(file.file, temp)
        temp_path = Path(temp.name)
    try:
        app_dir, manifest = packages.store_zip(slug, temp_path)
    except packages.PackageError as exc:
        raise HTTPException(400, str(exc)) from exc
    finally:
        temp_path.unlink(missing_ok=True)

    return _finish(db, app, manifest, app_dir, request, user_id)
